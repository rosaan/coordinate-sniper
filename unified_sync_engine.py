"""
Unified sync engine that processes queued operations from Convex.
Handles multiple operation types: create_user, get_mind_report, etc.
Only processes operations when they are queued by the server.
"""
import os
import sys
import time
from typing import Dict, Any, Optional
from convex import ConvexClient
from dotenv import load_dotenv
from sequences.create_user import create_user
from sequences.import_mind_report import import_mind_report
from local_db import LocalDB, UserStatus
from utils.mysql_check import check_patient_exists
from utils.file_upload import upload_file_to_convex
from utils import wait

# Load environment variables
load_dotenv(".env.local")

CONVEX_URL = os.getenv("CONVEX_URL")
if not CONVEX_URL:
    print("Error: CONVEX_URL not found in .env.local")
    print("Please set CONVEX_URL in .env.local file")
    sys.exit(1)


def report_error_to_server(client: ConvexClient, operation_id: str, error_msg: str, max_retries: int = 3) -> bool:
    """
    Report error to server with retry logic.
    
    Args:
        client: Convex client instance
        operation_id: Operation ID
        error_msg: Error message to report
        max_retries: Maximum number of retry attempts
        
    Returns:
        True if error was reported successfully, False otherwise
    """
    for attempt in range(max_retries):
        try:
            client.mutation("operations:updateOperationStatus", {
                "operationId": operation_id,
                "status": "failed",
                "errorReason": error_msg
            })
            print(f"    [✓] Error reported to server (attempt {attempt + 1})")
            return True
        except Exception as report_error:
            if attempt < max_retries - 1:
                print(f"    [!] Failed to report error to server (attempt {attempt + 1}/{max_retries}): {report_error}")
                wait(1.0)
            else:
                print(f"    [✗] CRITICAL: Failed to report error to server after {max_retries} attempts: {report_error}")
                print(f"    [✗] Original error was: {error_msg}")
                return False
    return False


def process_create_user_operation(operation: Dict[str, Any], user: Dict[str, Any], client: ConvexClient, db: LocalDB) -> None:
    """
    Process a create_user operation.
    
    Args:
        operation: Operation document
        user: User document
        client: Convex client instance
        db: Local database instance
    """
    operation_id = operation["_id"]
    user_id = user["_id"]
    client_code = user["clientCode"]
    first_name = user["firstName"]
    last_name = user.get("lastName", "") or ""
    
    # Check if already processed in local DB
    if db.is_user_processed(user_id):
        print(f"[+] Skipping user {user_id} - already processed locally")
        # Mark operation as completed
        try:
            client.mutation("operations:completeOperation", {"operationId": operation_id})
        except Exception:
            pass
        return
    
    # Add to local DB if not exists
    local_user = db.get_user(user_id)
    if not local_user:
        db.add_user(user_id, client_code, first_name, last_name)
    
    # Mark as processing
    db.update_status(user_id, UserStatus.PROCESSING)
    
    # Update operation status
    try:
        client.mutation("operations:updateOperationStatus", {
            "operationId": operation_id,
            "status": "processing"
        })
        client.mutation("user:updateSyncStatus", {
            "userId": user_id,
            "syncStatus": "processing"
        })
    except Exception:
        pass
    
    print(f"\n[+] Processing CREATE_USER operation: {first_name} {last_name} (ID: {user_id})")
    print(f"    Client Code: {client_code}")
    
    # Check MySQL database first
    print("    [*] Checking MySQL database for existing patient...")
    try:
        if check_patient_exists(client_code):
            print(f"    [✓] Patient already exists in MySQL - marking as completed")
            try:
                client.mutation("user:updateSyncStatus", {
                    "userId": user_id,
                    "syncStatus": "completed",
                    "errorReason": f"Patient already exists in MySQL database (PatientCode: {client_code})"
                })
                client.mutation("operations:completeOperation", {"operationId": operation_id})
            except Exception:
                pass
            db.update_status(user_id, UserStatus.COMPLETED, recording_link=None)
            return
    except Exception as e:
        print(f"    [!] Error checking MySQL: {e}, continuing with creation...")
    
    try:
        # Create user in VAEEG
        recording_link = create_user(
            client_id=client_code,
            first_name=first_name,
            last_name=last_name
        )
        
        if recording_link and recording_link.strip():
            print(f"    Recording link: {recording_link}")
            try:
                client.mutation("user:updateRecordingLink", {
                    "userId": user_id,
                    "recordingLink": recording_link
                })
                client.mutation("operations:completeOperation", {"operationId": operation_id})
                db.update_status(user_id, UserStatus.COMPLETED, recording_link=recording_link)
                print(f"    [✓] Successfully completed CREATE_USER operation")
            except Exception as e:
                print(f"    [!] Warning: Failed to update Convex: {e}")
                db.update_status(user_id, UserStatus.COMPLETED, recording_link=recording_link)
        else:
            error_msg = "Failed to get recording link (empty or None)"
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation_id, error_msg)
            db.update_status(user_id, UserStatus.FAILED, error_message=error_msg)
            
    except KeyboardInterrupt:
        try:
            client.mutation("operations:updateOperationStatus", {
                "operationId": operation_id,
                "status": "pending",
                "errorReason": "Interrupted by user"
            })
            client.mutation("user:updateSyncStatus", {
                "userId": user_id,
                "syncStatus": "pending",
                "errorReason": "Interrupted by user"
            })
        except Exception:
            pass
        db.update_status(user_id, UserStatus.PENDING, error_message="Interrupted by user")
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"    [✗] Error processing CREATE_USER: {error_msg}")
        report_error_to_server(client, operation_id, error_msg)
        db.update_status(user_id, UserStatus.FAILED, error_message=error_msg)
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)


def process_get_mind_report_operation(operation: Dict[str, Any], user: Dict[str, Any], client: ConvexClient) -> None:
    """
    Process a get_mind_report operation.
    
    Args:
        operation: Operation document
        user: User document
        client: Convex client instance
    """
    operation_id = operation["_id"]
    user_id = user["_id"]
    client_code = user["clientCode"]
    first_name = user["firstName"]
    
    # Update operation status to processing
    try:
        client.mutation("operations:updateOperationStatus", {
            "operationId": operation_id,
            "status": "processing"
        })
        client.mutation("user:updateMindReportStatus", {
            "userId": user_id,
            "status": "processing"
        })
    except Exception:
        pass
    
    print(f"\n[+] Processing GET_MIND_REPORT operation: {first_name} (ID: {user_id})")
    print(f"    Client Code: {client_code}")
    
    file_path = None
    file_link = None
    
    try:
        # Import mind report and export PDF
        print("    [*] Starting mind report import sequence...")
        try:
            file_path = import_mind_report(client_code=client_code)
        except RuntimeError as e:
            error_msg = f"MIND_REPORT_IMPORT_FAILED: {str(e)}"
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation_id, error_msg)
            return
        except Exception as e:
            import traceback
            tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            error_msg = (
                f"MIND_REPORT_IMPORT_UNEXPECTED: Unexpected error during mind report import sequence: {str(e)}. "
                f"Client code: {client_code}, User ID: {user_id}\nTraceback:\n{tb_str}"
            )
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation_id, error_msg)
            return
        
        # Verify file was created
        if not file_path or not os.path.exists(file_path):
            error_msg = (
                f"MIND_REPORT_EXPORT_FAILED: import_mind_report returned None or file doesn't exist. "
                f"Client code: {client_code}, File path: {file_path if file_path else 'None'}"
            )
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation_id, error_msg)
            return
        
        # Verify file is not empty
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                error_msg = f"MIND_REPORT_FILE_EMPTY: Exported file is empty (0 bytes): {file_path}"
                print(f"    [✗] {error_msg}")
                report_error_to_server(client, operation_id, error_msg)
                return
        except Exception as e:
            error_msg = f"MIND_REPORT_FILE_CHECK_ERROR: Error checking file size: {str(e)}. File path: {file_path}"
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation_id, error_msg)
            return
        
        print(f"    [✓] Mind report PDF exported: {file_path} ({os.path.getsize(file_path)} bytes)")
        
        # Upload file to server
        print("    [*] Uploading file to server...")
        try:
            file_link = upload_file_to_convex(file_path, CONVEX_URL, client)
        except Exception as e:
            import traceback
            tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            error_msg = (
                f"MIND_REPORT_UPLOAD_ERROR: Error uploading file to server: {str(e)}. "
                f"File path: {file_path}, Client code: {client_code}\nTraceback:\n{tb_str}"
            )
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation_id, error_msg)
            return
        
        if not file_link:
            error_msg = f"MIND_REPORT_UPLOAD_FAILED: File upload returned None or empty. File path: {file_path}"
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation_id, error_msg)
            return
        
        print(f"    [✓] File uploaded: {file_link}")
        
        # Save link in database
        print("    [*] Saving file link to database...")
        try:
            client.mutation("user:updateMindReportLink", {
                "userId": user_id,
                "fileLink": file_link
            })
            client.mutation("operations:completeOperation", {"operationId": operation_id})
            print(f"    [✓] File link saved to database")
        except Exception as update_error:
            import traceback
            tb_str = ''.join(traceback.format_exception(type(update_error), update_error, update_error.__traceback__))
            error_msg = (
                f"MIND_REPORT_DB_SAVE_ERROR: Failed to save file link to database: {str(update_error)}. "
                f"File link: {file_link}, File path: {file_path}\nTraceback:\n{tb_str}"
            )
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation_id, error_msg)
            return
        
        print(f"    [✓] GET_MIND_REPORT operation completed successfully")
        
    except KeyboardInterrupt:
        error_msg = "MIND_REPORT_INTERRUPTED: Process interrupted by user"
        print(f"    [*] {error_msg}")
        try:
            client.mutation("operations:updateOperationStatus", {
                "operationId": operation_id,
                "status": "pending",
                "errorReason": error_msg
            })
            client.mutation("user:updateMindReportStatus", {
                "userId": user_id,
                "status": "pending",
                "errorReason": error_msg
            })
        except Exception:
            pass
        raise
    except Exception as e:
        import traceback
        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        error_msg = (
            f"MIND_REPORT_UNEXPECTED_ERROR: Unexpected error during mind report processing: {str(e)}. "
            f"Client code: {client_code}, User ID: {user_id}, "
            f"File path: {file_path if file_path else 'not created'}, "
            f"File link: {file_link if file_link else 'not uploaded'}\nTraceback:\n{tb_str}"
        )
        print(f"    [✗] {error_msg}")
        report_error_to_server(client, operation_id, error_msg)
        traceback.print_exception(type(e), e, e.__traceback__)


def process_operation(operation: Dict[str, Any], client: ConvexClient, db: Optional[LocalDB] = None) -> None:
    """
    Process a single operation based on its type.
    
    Args:
        operation: Operation document from Convex
        client: Convex client instance
        db: Local database instance (required for create_user operations)
    """
    operation_type = operation["operationType"]
    user = operation["user"]
    
    print(f"\n[+] Processing operation: {operation_type} (Operation ID: {operation['_id']})")
    
    try:
        if operation_type == "create_user":
            if db is None:
                raise RuntimeError("LocalDB required for create_user operations")
            process_create_user_operation(operation, user, client, db)
        elif operation_type == "get_mind_report":
            process_get_mind_report_operation(operation, user, client)
        else:
            error_msg = f"Unknown operation type: {operation_type}"
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, operation["_id"], error_msg)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        error_msg = f"CRITICAL_ERROR_IN_PROCESSING: {str(e)}"
        print(f"    [✗] {error_msg}")
        report_error_to_server(client, operation["_id"], error_msg)
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)


def sync_loop(client: ConvexClient, db: Optional[LocalDB] = None) -> None:
    """
    Main sync loop that subscribes to pending operations and processes them.
    
    Args:
        client: Convex client instance
        db: Local database instance (optional, required for create_user operations)
    """
    print("[+] Starting unified sync engine...")
    print(f"[+] Connected to Convex: {CONVEX_URL}")
    if db:
        print(f"[+] Local database: {db.db_path}")
    print("[+] Listening for queued operations...")
    print("[+] Supported operations: create_user, get_mind_report")
    print("[+] Press Ctrl+C to stop\n")
    
    try:
        # Subscribe to pending operations query
        for operations in client.subscribe("operations:listPendingOperations"):
            if not operations:
                continue
            
            # Process each operation
            for operation in operations:
                operation_id = operation["_id"]
                operation_type = operation["operationType"]
                status = operation.get("status")
                
                # Skip if not pending (shouldn't happen, but safety check)
                if status != "pending":
                    continue
                
                # Process the operation
                try:
                    process_operation(operation, client, db)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"\n[✗] CRITICAL: Failed to process operation {operation_id} ({operation_type})")
                    print(f"[✗] Error: {str(e)}")
                    import traceback
                    traceback.print_exception(type(e), e, e.__traceback__)
                    print("[*] Continuing with next operation...\n")
                
                # Wait before processing next operation (allows VAEEG to stabilize)
                print("[+] Waiting 3 seconds before next operation (allowing VAEEG to stabilize)...")
                time.sleep(3)
                
    except KeyboardInterrupt:
        print("\n[+] Unified sync engine stopped by user")
    except Exception as e:
        print(f"\n[✗] Unified sync engine error: {str(e)}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)


def verify_setup(client: ConvexClient) -> bool:
    """
    Verify that Convex connection is working.
    
    Args:
        client: Convex client instance
        
    Returns:
        True if setup is valid, False otherwise
    """
    print("[+] Verifying Convex connection...")
    try:
        test_result = client.query("operations:listPendingOperations")
        print(f"[✓] Convex connection verified (found {len(test_result)} pending operations)")
        return True
    except Exception as e:
        print(f"[✗] Failed to verify Convex connection: {e}")
        print(f"[!] Make sure:")
        print(f"    1. CONVEX_URL is correct in .env.local")
        print(f"    2. Convex dev server is running (npx convex dev)")
        print(f"    3. The 'operations:listPendingOperations' query exists in convex/operations.ts")
        return False


def main():
    """Main entry point for the unified sync engine."""
    print("=" * 60)
    print("VAEEG Unified Sync Engine")
    print("=" * 60)
    
    # Initialize Convex client
    client = ConvexClient(CONVEX_URL)
    
    # Initialize local database (for create_user operations)
    db = LocalDB()
    print(f"[✓] Local database initialized: {db.db_path}")
    
    # Verify setup
    if not verify_setup(client):
        print("\n[✗] Setup verification failed. Please fix the issues above.")
        sys.exit(1)
    
    print()
    
    # Start sync loop
    sync_loop(client, db)


if __name__ == "__main__":
    main()

