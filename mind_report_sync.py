"""
Mind Report Sync Engine - watches Convex for users needing mind report import
and processes them by exporting PDFs and uploading to server.
"""
import os
import sys
import time
from typing import Dict, Any
from convex import ConvexClient
from dotenv import load_dotenv
from sequences.import_mind_report import import_mind_report
from utils.file_upload import upload_file_to_convex
from utils import wait

# Load environment variables
load_dotenv(".env.local")

CONVEX_URL = os.getenv("CONVEX_URL")
if not CONVEX_URL:
    print("Error: CONVEX_URL not found in .env.local")
    print("Please set CONVEX_URL in .env.local file")
    sys.exit(1)


def report_error_to_server(client: ConvexClient, user_id: str, error_msg: str, max_retries: int = 3) -> bool:
    """
    Report error to server with retry logic.
    
    Args:
        client: Convex client instance
        user_id: User ID
        error_msg: Error message to report
        max_retries: Maximum number of retry attempts
        
    Returns:
        True if error was reported successfully, False otherwise
    """
    for attempt in range(max_retries):
        try:
            client.mutation("user:updateMindReportStatus", {
                "userId": user_id,
                "status": "failed",
                "errorReason": error_msg
            })
            print(f"    [✓] Error reported to server (attempt {attempt + 1})")
            return True
        except Exception as report_error:
            if attempt < max_retries - 1:
                print(f"    [!] Failed to report error to server (attempt {attempt + 1}/{max_retries}): {report_error}")
                wait(1.0)  # Wait before retry
            else:
                print(f"    [✗] CRITICAL: Failed to report error to server after {max_retries} attempts: {report_error}")
                print(f"    [✗] Original error was: {error_msg}")
                return False
    return False


def process_mind_report(user: Dict[str, Any], client: ConvexClient) -> None:
    """
    Process a single user's mind report import.
    
    Args:
        user: User document from Convex
        client: Convex client instance
    """
    user_id = user["_id"]
    client_code = user["clientCode"]
    first_name = user["firstName"]
    
    # Mark as processing - report to server
    processing_reported = False
    try:
        client.mutation("user:updateMindReportStatus", {
            "userId": user_id,
            "status": "processing"
        })
        processing_reported = True
        print(f"    [✓] Status updated to 'processing' on server")
    except Exception as e:
        print(f"    [!] Warning: Failed to update status to 'processing': {e}")
        # Continue anyway - we'll try to report errors later
    
    print(f"\n[+] Processing mind report for user: {first_name} (ID: {user_id})")
    print(f"    Client Code: {client_code}")
    
    file_path = None
    file_link = None
    
    try:
        # Step 1: Import mind report and export PDF
        print("    [*] Starting mind report import sequence...")
        try:
            file_path = import_mind_report(client_code=client_code)
        except RuntimeError as e:
            # RuntimeError from import_mind_report already has detailed message
            error_msg = f"MIND_REPORT_IMPORT_FAILED: {str(e)}"
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, user_id, error_msg)
            return
        except Exception as e:
            # Unexpected error during import
            import traceback
            tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            error_msg = (
                f"MIND_REPORT_IMPORT_UNEXPECTED: Unexpected error during mind report import sequence: {str(e)}. "
                f"Client code: {client_code}, User ID: {user_id}\nTraceback:\n{tb_str}"
            )
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, user_id, error_msg)
            return
        
        # Verify file was created
        if not file_path:
            error_msg = f"MIND_REPORT_EXPORT_FAILED: import_mind_report returned None for client code: {client_code}"
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, user_id, error_msg)
            return
        
        if not os.path.exists(file_path):
            error_msg = (
                f"MIND_REPORT_FILE_MISSING: Exported file does not exist: {file_path}. "
                f"Client code: {client_code}"
            )
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, user_id, error_msg)
            return
        
        # Verify file is not empty
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                error_msg = (
                    f"MIND_REPORT_FILE_EMPTY: Exported file is empty (0 bytes): {file_path}. "
                    f"Client code: {client_code}"
                )
                print(f"    [✗] {error_msg}")
                report_error_to_server(client, user_id, error_msg)
                return
        except Exception as e:
            error_msg = (
                f"MIND_REPORT_FILE_CHECK_ERROR: Error checking file size: {str(e)}. "
                f"File path: {file_path}, Client code: {client_code}"
            )
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, user_id, error_msg)
            return
        
        print(f"    [✓] Mind report PDF exported: {file_path} ({os.path.getsize(file_path)} bytes)")
        
        # Step 2: Upload file to server
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
            report_error_to_server(client, user_id, error_msg)
            return
        
        if not file_link:
            error_msg = (
                f"MIND_REPORT_UPLOAD_FAILED: File upload returned None or empty. "
                f"File path: {file_path}, Client code: {client_code}"
            )
            print(f"    [✗] {error_msg}")
            report_error_to_server(client, user_id, error_msg)
            return
        
        print(f"    [✓] File uploaded: {file_link}")
        
        # Step 3: Save link in database
        print("    [*] Saving file link to database...")
        try:
            client.mutation("user:updateMindReportLink", {
                "userId": user_id,
                "fileLink": file_link
            })
            print(f"    [✓] File link saved to database")
        except Exception as update_error:
            import traceback
            tb_str = ''.join(traceback.format_exception(type(update_error), update_error, update_error.__traceback__))
            error_msg = (
                f"MIND_REPORT_DB_SAVE_ERROR: Failed to save file link to database: {str(update_error)}. "
                f"File link: {file_link}, File path: {file_path}, Client code: {client_code}\nTraceback:\n{tb_str}"
            )
            print(f"    [✗] {error_msg}")
            # File was uploaded but link wasn't saved - still report as failed
            report_error_to_server(client, user_id, error_msg)
            return
        
        print(f"    [✓] Mind report import completed successfully for user {user_id}")
        
    except KeyboardInterrupt:
        # User wants to stop - reset status
        error_msg = "MIND_REPORT_INTERRUPTED: Process interrupted by user"
        print(f"    [*] {error_msg}")
        try:
            client.mutation("user:updateMindReportStatus", {
                "userId": user_id,
                "status": "pending",
                "errorReason": error_msg
            })
            print(f"    [✓] Status reset to 'pending' on server")
        except Exception as reset_error:
            print(f"    [✗] Failed to reset status: {reset_error}")
        raise
    except Exception as e:
        # Catch-all for any unexpected errors
        import traceback
        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        error_msg = (
            f"MIND_REPORT_UNEXPECTED_ERROR: Unexpected error during mind report processing: {str(e)}. "
            f"Client code: {client_code}, User ID: {user_id}, "
            f"File path: {file_path if file_path else 'not created'}, "
            f"File link: {file_link if file_link else 'not uploaded'}\nTraceback:\n{tb_str}"
        )
        print(f"    [✗] {error_msg}")
        report_error_to_server(client, user_id, error_msg)
        
        # Print traceback for debugging
        traceback.print_exception(type(e), e, e.__traceback__)


def sync_loop(client: ConvexClient) -> None:
    """
    Main sync loop that subscribes to pending mind reports and processes them.
    
    Args:
        client: Convex client instance
    """
    print("[+] Starting mind report sync engine...")
    print(f"[+] Connected to Convex: {CONVEX_URL}")
    print("[+] Listening for users needing mind report import...")
    print("[+] Press Ctrl+C to stop\n")
    
    try:
        # Subscribe to pending mind reports query
        for users in client.subscribe("user:listPendingMindReports"):
            if not users:
                continue
            
            # Process each user
            for user in users:
                user_id = user["_id"]
                mind_report_status = user.get("mindReportStatus")
                
                # Skip if already processing or completed
                if mind_report_status == "processing" or mind_report_status == "completed":
                    continue
                
                # Process the user
                try:
                    process_mind_report(user, client)
                except KeyboardInterrupt:
                    # Re-raise keyboard interrupt to stop the loop
                    raise
                except Exception as e:
                    # Log error but continue processing other users
                    user_id = user.get("_id", "unknown")
                    client_code = user.get("clientCode", "unknown")
                    print(f"\n[✗] CRITICAL: Failed to process mind report for user {user_id} (client code: {client_code})")
                    print(f"[✗] Error: {str(e)}")
                    import traceback
                    traceback.print_exception(type(e), e, e.__traceback__)
                    # Try to report error to server one more time
                    try:
                        report_error_to_server(client, user_id, f"CRITICAL_ERROR_IN_PROCESSING: {str(e)}")
                    except Exception:
                        pass
                    print("[*] Continuing with next user...\n")
                
                # Wait before processing next user (allows VAEEG to stabilize)
                print("[+] Waiting 3 seconds before next user (allowing VAEEG to stabilize)...")
                time.sleep(3)
                
    except KeyboardInterrupt:
        print("\n[+] Mind report sync engine stopped by user")
    except Exception as e:
        print(f"\n[✗] Mind report sync engine error: {str(e)}")
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
        # Test query to verify connection
        test_result = client.query("user:listPendingMindReports")
        print(f"[✓] Convex connection verified (found {len(test_result)} pending mind reports)")
        return True
    except Exception as e:
        print(f"[✗] Failed to verify Convex connection: {e}")
        print(f"[!] Make sure:")
        print(f"    1. CONVEX_URL is correct in .env.local")
        print(f"    2. Convex dev server is running (npx convex dev)")
        print(f"    3. The 'user:listPendingMindReports' query exists in convex/user.ts")
        return False


def main():
    """Main entry point for the mind report sync engine."""
    print("=" * 60)
    print("VAEEG Mind Report Sync Engine")
    print("=" * 60)
    
    # Initialize Convex client
    client = ConvexClient(CONVEX_URL)
    
    # Verify setup
    if not verify_setup(client):
        print("\n[✗] Setup verification failed. Please fix the issues above.")
        sys.exit(1)
    
    print()
    
    # Start sync loop
    sync_loop(client)


if __name__ == "__main__":
    main()

