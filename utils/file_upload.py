"""
File upload utilities for uploading files to Convex storage.
"""
import os
import requests
from typing import Optional
from convex import ConvexClient


def upload_file_to_convex(file_path: str, convex_url: str, convex_client: Optional[ConvexClient] = None) -> Optional[str]:
    """
    Upload a file to Convex storage and return the file URL.
    
    Note: Convex file storage requires using HTTP API. This function uploads the file
    and returns a storage ID that can be used to generate a URL.
    
    Args:
        file_path: Path to the file to upload
        convex_url: Convex deployment URL
        convex_client: Optional ConvexClient instance (if already connected)
        
    Returns:
        Storage ID or file URL, or None if upload failed
        
    Raises:
        FileNotFoundError: If file does not exist
        RuntimeError: If upload fails with detailed error message
    """
    if not os.path.exists(file_path):
        error_msg = f"FILE_UPLOAD_ERROR_FILE_NOT_FOUND: File not found: {file_path}"
        print(f"[!] {error_msg}")
        raise FileNotFoundError(error_msg)
    
    try:
        # Verify file is readable and not empty
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            error_msg = f"FILE_UPLOAD_ERROR_FILE_EMPTY: File is empty (0 bytes): {file_path}"
            print(f"[!] {error_msg}")
            raise RuntimeError(error_msg)
        
        # For now, we'll store the local file path or return a placeholder
        # Full Convex file upload integration would require:
        # 1. Getting an upload URL from Convex
        # 2. Uploading the file via HTTP PUT/POST
        # 3. Getting the storage ID back
        
        # TODO: Implement full Convex file upload using HTTP API
        # For now, return the local file path as a placeholder
        # In production, this should upload to Convex storage and return the storage ID
        
        print(f"[*] File upload not fully implemented - returning local path")
        print(f"[*] File: {file_path} ({file_size} bytes)")
        print(f"[!] TODO: Implement Convex file upload via HTTP API")
        
        # Return a file:// URL for now
        return f"file://{os.path.abspath(file_path)}"
        
    except (FileNotFoundError, RuntimeError):
        # Re-raise expected errors
        raise
    except Exception as e:
        error_msg = (
            f"FILE_UPLOAD_ERROR_UNEXPECTED: Unexpected error uploading file: {str(e)}. "
            f"File path: {file_path}, Convex URL: {convex_url}"
        )
        print(f"[!] {error_msg}")
        raise RuntimeError(error_msg) from e


def upload_file_via_http(file_path: str, upload_url: str) -> Optional[str]:
    """
    Upload a file via HTTP PUT/POST to a given URL.
    
    Args:
        file_path: Path to the file to upload
        upload_url: URL to upload the file to
        
    Returns:
        Response content (usually storage ID) or None if failed
    """
    if not os.path.exists(file_path):
        print(f"[!] File not found: {file_path}")
        return None
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            response = requests.post(upload_url, files=files, timeout=60)
            
            if response.status_code == 200:
                return response.text
            else:
                print(f"[!] Upload failed with status {response.status_code}: {response.text}")
                return None
                
    except Exception as e:
        print(f"[!] Error uploading file via HTTP: {e}")
        return None

