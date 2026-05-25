"""
Optional helper: run schema.sql against MySQL.
Usage: python init_db.py
Requires MySQL running (XAMPP) and .env configured.
"""

import os
import sys

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("MYSQL_HOST", "localhost")
PORT = int(os.getenv("MYSQL_PORT", "3306"))
USER = os.getenv("MYSQL_USER", "root")
PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DATABASE = os.getenv("MYSQL_DATABASE", "rqms_db")

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "database", "schema.sql")


def main():
    print("RQMS — Initialize MySQL database")
    print(f"Host: {HOST}:{PORT}  User: {USER}  Database: {DATABASE}")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    # Connect without database first to create DB
    conn = mysql.connector.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD
    )
    cursor = conn.cursor()

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        try:
            cursor.execute(stmt)
        except mysql.connector.Error as ex:
            if "already exists" not in str(ex).lower():
                print(f"Warning: {ex}")
    conn.commit()
    cursor.close()
    conn.close()
    print("Done. Schema applied. Start the app with: python app.py")


if __name__ == "__main__":
    main()
    sys.exit(0)
