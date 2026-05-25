"""MySQL connection helper for RQMS."""

import mysql.connector
from mysql.connector import Error

from config import Config


def get_connection():
    """Open a new MySQL connection using config from .env."""
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
    )


def ensure_result_columns():
    """Add required schema to existing databases (safe to run repeatedly)."""
    columns = [
        ("patient_phone", "VARCHAR(30) NULL"),
        ("patient_priority", "VARCHAR(20) DEFAULT 'Regular'"),
        ("sms_enabled", "TINYINT(1) DEFAULT 0"),
        ("reminder_sent", "TINYINT(1) DEFAULT 0"),
        ("result_status", "VARCHAR(30) DEFAULT '—'"),
        ("result_ready_at", "DATETIME NULL"),
        ("result_released_at", "DATETIME NULL"),
        ("result_notify_sent", "TINYINT(1) DEFAULT 0"),
    ]
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS room_catalog (
                room_id INT AUTO_INCREMENT PRIMARY KEY,
                room_name VARCHAR(50) NOT NULL UNIQUE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS service_catalog (
                service_id INT AUTO_INCREMENT PRIMARY KEY,
                service_name VARCHAR(50) NOT NULL UNIQUE
            )
            """
        )

        for name, definition in columns:
            try:
                cursor.execute(f"ALTER TABLE queue_patients ADD COLUMN {name} {definition}")
                conn.commit()
            except Error as ex:
                if ex.errno != 1060:
                    raise

        conn.commit()
        cursor.close()
        conn.close()
    except Error:
        pass


def test_connection():
    """Return (success, message) for database health check."""
    try:
        conn = get_connection()
        if conn.is_connected():
            db_name = Config.MYSQL_DATABASE
            conn.close()
            return True, f"MySQL connected — database: {db_name}"
    except Error as ex:
        return False, str(ex)
    return False, "Unknown connection error"
