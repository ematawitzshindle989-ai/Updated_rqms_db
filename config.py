import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "rqms-dev-secret-change-in-production")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "rqms_db")
    SIM800C_PORT = os.getenv("SIM800C_PORT", "COM3")
    SIM800C_BAUDRATE = int(os.getenv("SIM800C_BAUDRATE", "9600"))
    SIM800C_TIMEOUT = float(os.getenv("SIM800C_TIMEOUT", "5"))
    SMS_MODE = os.getenv("SMS_MODE", "sim800c").strip().lower()
