"""
SQLite database for tracking local user processing state.
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class UserStatus(str, Enum):
    """Status of user processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LocalDB:
    """SQLite database for tracking user processing state."""
    
    def __init__(self, db_path: str = "local_state.db"):
        """
        Initialize the local database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                client_code TEXT NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                recording_link TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON users(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id ON users(user_id)
        """)
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: str, client_code: str, first_name: str, 
                 last_name: Optional[str] = None) -> None:
        """
        Add a new user to track.
        
        Args:
            user_id: Convex user ID
            client_code: Client code
            first_name: First name
            last_name: Last name (optional)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO users 
            (user_id, client_code, first_name, last_name, status)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, client_code, first_name, last_name, UserStatus.PENDING))
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID.
        
        Args:
            user_id: Convex user ID
            
        Returns:
            User record or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_status(self, user_id: str, status: UserStatus, 
                     recording_link: Optional[str] = None,
                     error_message: Optional[str] = None) -> None:
        """
        Update user status.
        
        Args:
            user_id: Convex user ID
            status: New status
            recording_link: Recording link if completed
            error_message: Error message if failed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        processed_at = datetime.now().isoformat() if status in [UserStatus.COMPLETED, UserStatus.FAILED] else None
        
        cursor.execute("""
            UPDATE users 
            SET status = ?, 
                recording_link = ?,
                error_message = ?,
                processed_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (status.value, recording_link, error_message, processed_at, user_id))
        
        conn.commit()
        conn.close()
    
    def increment_retry(self, user_id: str) -> int:
        """
        Increment retry count for a user.
        
        Args:
            user_id: Convex user ID
            
        Returns:
            New retry count
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET retry_count = retry_count + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))
        
        cursor.execute("SELECT retry_count FROM users WHERE user_id = ?", (user_id,))
        retry_count = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return retry_count
    
    def get_pending_users(self) -> List[Dict[str, Any]]:
        """
        Get all users with pending status.
        
        Returns:
            List of pending user records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM users 
            WHERE status = ? 
            ORDER BY created_at ASC
        """, (UserStatus.PENDING,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_failed_users(self, max_retries: int = 3) -> List[Dict[str, Any]]:
        """
        Get failed users that can be retried.
        
        Args:
            max_retries: Maximum retry count
            
        Returns:
            List of failed user records that can be retried
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM users 
            WHERE status = ? AND retry_count < ?
            ORDER BY updated_at ASC
        """, (UserStatus.FAILED, max_retries))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def is_user_processed(self, user_id: str) -> bool:
        """
        Check if a user has been processed (completed or failed beyond retries).
        
        Args:
            user_id: Convex user ID
            
        Returns:
            True if user is processed, False otherwise
        """
        user = self.get_user(user_id)
        if not user:
            return False
        
        return user["status"] == UserStatus.COMPLETED
    
    def reset_user(self, user_id: str) -> None:
        """
        Reset a user to pending status (for retry).
        
        Args:
            user_id: Convex user ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET status = ?,
                processed_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (UserStatus.PENDING, user_id))
        
        conn.commit()
        conn.close()
    
    def cleanup_old_records(self, days: int = 30) -> int:
        """
        Clean up old completed records.
        
        Args:
            days: Number of days to keep records
            
        Returns:
            Number of records deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM users 
            WHERE status = ? 
            AND processed_at < datetime('now', '-' || ? || ' days')
        """, (UserStatus.COMPLETED, days))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted

