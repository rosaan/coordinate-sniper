"""
MySQL database check utilities for VAEEG.
Checks if a patient already exists in the local MySQL database.
"""
import pymysql
from typing import Optional


MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "va",
    "charset": "utf8",  # MySQL 4.x does not understand utf8mb4; utf8 is the safest wide charset it supports
    "use_unicode": True,
}


def check_patient_exists(client_code: str) -> bool:
    """
    Check if a patient with the given PatientCode already exists in MySQL database.
    
    Args:
        client_code: Client code (PatientCode) to check
        
    Returns:
        True if patient exists, False otherwise
    """
    try:
        # Connect to MySQL database
        connection = pymysql.connect(**MYSQL_CONFIG)
        
        try:
            with connection.cursor() as cursor:
                # Query patientt table for PatientCode
                sql = "SELECT COUNT(*) FROM patientt WHERE PatientCode = %s"
                cursor.execute(sql, (client_code,))
                result = cursor.fetchone()
                
                if result and result[0] > 0:
                    print(f"    [✓] Patient with PatientCode '{client_code}' already exists in MySQL database")
                    return True
                else:
                    print(f"    [*] Patient with PatientCode '{client_code}' not found in MySQL database")
                    return False
        finally:
            connection.close()
            
    except pymysql.Error as e:
        print(f"    [!] MySQL error checking patient: {e}")
        # If we can't check, assume patient doesn't exist (safer to try creating)
        return False
    except Exception as e:
        print(f"    [!] Error checking MySQL database: {e}")
        # If we can't check, assume patient doesn't exist (safer to try creating)
        return False


def test_mysql_connection() -> bool:
    """
    Test MySQL database connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        connection = pymysql.connect(**MYSQL_CONFIG)
        connection.close()
        print("[✓] MySQL connection successful")
        return True
    except Exception as e:
        print(f"[!] MySQL connection failed: {e}")
        print("[!] Make sure MySQL is running and database 'va' exists")
        return False
