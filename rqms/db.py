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
    """Apply additive schema upgrades required by the application."""
    columns = [
        ("patient_phone", "VARCHAR(30) NULL"),
        ("patient_priority", "VARCHAR(20) DEFAULT 'Regular'"),
        ("sms_enabled", "TINYINT(1) DEFAULT 0"),
        ("reminder_sent", "TINYINT(1) DEFAULT 0"),
        ("result_status", "VARCHAR(30) DEFAULT '—'"),
        ("result_ready_at", "DATETIME NULL"),
        ("result_released_at", "DATETIME NULL"),
        ("result_notify_sent", "TINYINT(1) DEFAULT 0"),
        ("reminder_status", "VARCHAR(20) DEFAULT 'Not Sent'"),
        ("reminder_sent_at", "DATETIME NULL"),
        ("turn_notification_status", "VARCHAR(20) DEFAULT 'Not Sent'"),
        ("turn_notification_sent_at", "DATETIME NULL"),
    ]
    conn = get_connection()
    cursor = None
    try:
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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS emergency_cases (
                emergency_id INT AUTO_INCREMENT PRIMARY KEY,
                activated_at DATETIME NOT NULL,
                deactivated_at DATETIME NULL,
                activated_by INT NULL,
                deactivated_by INT NULL,
                sms_notification_started_at DATETIME NULL,
                INDEX idx_emergency_active (deactivated_at),
                CONSTRAINT fk_emergency_activated_by
                    FOREIGN KEY (activated_by) REFERENCES users(user_id),
                CONSTRAINT fk_emergency_deactivated_by
                    FOREIGN KEY (deactivated_by) REFERENCES users(user_id)
            )
            """
        )
        cursor.execute(
            "SHOW COLUMNS FROM emergency_cases LIKE %s",
            ("sms_notification_started_at",),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                """
                ALTER TABLE emergency_cases
                ADD COLUMN sms_notification_started_at DATETIME NULL
                """
            )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sms_notification_log (
                sms_log_id INT AUTO_INCREMENT PRIMARY KEY,
                queue_id INT NULL,
                patient_name VARCHAR(100) NOT NULL,
                recipient VARCHAR(30) NOT NULL,
                notification_type VARCHAR(30) NOT NULL,
                message TEXT NOT NULL,
                status VARCHAR(30) NOT NULL,
                sent_at DATETIME NOT NULL,
                INDEX idx_sms_log_queue (queue_id),
                INDEX idx_sms_log_sent_at (sent_at)
            )
            """
        )

        cursor.execute("ALTER TABLE users MODIFY COLUMN password VARCHAR(255) NOT NULL")
        cursor.execute("SHOW COLUMNS FROM users LIKE %s", ("is_active",))
        if cursor.fetchone() is None:
            cursor.execute(
                """
                ALTER TABLE users
                ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1
                """
            )

        for name, definition in columns:
            cursor.execute("SHOW COLUMNS FROM queue_patients LIKE %s", (name,))
            if cursor.fetchone() is None:
                cursor.execute(
                    f"ALTER TABLE queue_patients ADD COLUMN {name} {definition}"
                )
        conn.commit()
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


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
