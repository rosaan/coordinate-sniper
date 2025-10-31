"""
Local sync engine that watches Convex for new users and creates them in VAEEG.
Uses SQLite for local state tracking.
"""
import os
import sys
from typing import Dict, Any, List
from convex import ConvexClient
from dotenv import load_dotenv
from sequences.create_user import create_user
from local_db import LocalDB, UserStatus

# Load environment variables
load_dotenv(".env.local")

CONVEX_URL = os.getenv("CONVEX_URL")
if not CONVEX_URL:
    print("Error: CONVEX_URL not found in .env.local")
    print("Please set CONVEX_URL in .env.local file")
    sys.exit(1)


def process_user(user: Dict[str, Any], client: ConvexClient, db: LocalDB) -> None:
    """
    Process a single user by creating them in VAEEG and updating Convex.
    
    Args:
        user: User document from Convex
        client: Convex client instance
        db: Local database instance
    """
    user_id = user["_id"]
    client_code = user["clientCode"]
    first_name = user["firstName"]
    last_name = user.get("lastName", "") or ""
    
    # Check if already processed in local DB
    if db.is_user_processed(user_id):
        print(f"[+] Skipping user {user_id} - already processed locally")
        return
    
    # Add to local DB if not exists
    local_user = db.get_user(user_id)
    if not local_user:
        db.add_user(user_id, client_code, first_name, last_name)
    
    # Mark as processing
    db.update_status(user_id, UserStatus.PROCESSING)
    
    print(f"\n[+] Processing user: {first_name} {last_name} (ID: {user_id})")
    print(f"    Client Code: {client_code}")
    
    try:
        # Create user in VAEEG and get recording link
        recording_link = create_user(
            client_id=client_code,
            first_name=first_name,
            last_name=last_name
        )
        
        if recording_link:
            print(f"    Recording link: {recording_link}")
            
            # Update user in Convex with the recording link
            client.mutation("user:updateRecordingLink", {
                "userId": user_id,
                "recordingLink": recording_link
            })
            
            # Update local DB
            db.update_status(user_id, UserStatus.COMPLETED, recording_link=recording_link)
            
            print(f"    [✓] Successfully updated user {user_id} with recording link")
        else:
            error_msg = "Failed to get recording link"
            print(f"    [✗] {error_msg} for user {user_id}")
            retry_count = db.increment_retry(user_id)
            db.update_status(user_id, UserStatus.FAILED, error_message=error_msg)
            print(f"    Retry count: {retry_count}")
            
    except Exception as e:
        error_msg = str(e)
        print(f"    [✗] Error processing user {user_id}: {error_msg}")
        retry_count = db.increment_retry(user_id)
        db.update_status(user_id, UserStatus.FAILED, error_message=error_msg)
        print(f"    Retry count: {retry_count}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)


def sync_loop(client: ConvexClient, db: LocalDB) -> None:
    """
    Main sync loop that subscribes to pending users and processes them.
    
    Args:
        client: Convex client instance
        db: Local database instance
    """
    print("[+] Starting sync engine...")
    print(f"[+] Connected to Convex: {CONVEX_URL}")
    print(f"[+] Local database: {db.db_path}")
    print("[+] Listening for new users...")
    print("[+] Press Ctrl+C to stop\n")
    
    # Sync existing users from Convex to local DB
    print("[+] Syncing existing users to local database...")
    try:
        existing_users = client.query("user:listPendingUsers")
        for user in existing_users:
            if not db.get_user(user["_id"]):
                db.add_user(
                    user["_id"],
                    user["clientCode"],
                    user["firstName"],
                    user.get("lastName")
                )
        print(f"[+] Synced {len(existing_users)} users to local database\n")
    except Exception as e:
        print(f"[!] Warning: Could not sync existing users: {e}\n")
    
    try:
        # Subscribe to pending users query
        for users in client.subscribe("user:listPendingUsers"):
            if not users:
                continue
            
            # Process each user
            for user in users:
                user_id = user["_id"]
                
                # Skip if already completed in local DB
                if db.is_user_processed(user_id):
                    continue
                
                # Process the user
                process_user(user, client, db)
                
    except KeyboardInterrupt:
        print("\n[+] Sync engine stopped by user")
    except Exception as e:
        print(f"\n[✗] Sync engine error: {str(e)}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)


def verify_setup(client: ConvexClient) -> bool:
    """
    Verify that Convex connection and functions are working.
    
    Args:
        client: Convex client instance
        
    Returns:
        True if setup is valid, False otherwise
    """
    print("[+] Verifying Convex connection...")
    try:
        # Test query to verify connection
        test_result = client.query("user:listPendingUsers")
        print(f"[✓] Convex connection verified (found {len(test_result)} pending users)")
        return True
    except Exception as e:
        print(f"[✗] Failed to verify Convex connection: {e}")
        print(f"[!] Make sure:")
        print(f"    1. CONVEX_URL is correct in .env.local")
        print(f"    2. Convex dev server is running (npx convex dev)")
        print(f"    3. The 'user:listPendingUsers' query exists in convex/user.ts")
        return False


def main():
    """Main entry point for the sync engine."""
    print("=" * 60)
    print("VAEEG User Sync Engine")
    print("=" * 60)
    
    # Initialize Convex client
    client = ConvexClient(CONVEX_URL)
    
    # Initialize local database
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

