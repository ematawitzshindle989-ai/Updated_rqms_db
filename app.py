"""
RQMS — Radiology Queue Management System
St. Paul Hospital | Python Flask + MySQL + HTML/CSS/JavaScript

Run: python app.py
"""

from rqms import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
