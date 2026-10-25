# RQMS — Python Flask + MySQL + Web Frontend

**Radiology Queue Management and Patient Notification System**  
St. Paul Hospital | Capstone website project

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | **Python 3** + **Flask** |
| Database | **MySQL** (XAMPP) |
| Frontend | **HTML**, **external CSS**, **JavaScript** |
| Editor | **Visual Studio Code** |

## Prerequisites

1. **Python 3.10+** — [python.org](https://www.python.org/)
2. **XAMPP** (or MySQL Server) — Apache + MySQL running
3. **VS Code** — optional Live Server not required (Flask serves pages)

## Setup (first time)

### 1. Install Python packages

```bash
cd RadiologyQueueManagementSystem-Web
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure MySQL

Copy `.env.example` to `.env` and set your MySQL password:

```
MYSQL_PASSWORD=your_xampp_password
```

### 3. Create database

**Option A — phpMyAdmin:** Import `database/schema.sql`

**Option B — command line:**

```bash
python init_db.py
```

For an existing database, run `database/migration_emergency.sql` and
`database/migration_sms.sql` once, or start Flask to apply the safe column/table
upgrades automatically.

The startup schema upgrade also adds Staff account activation and expands the
password column for hashed passwords. Alternatively, run
`database/migration_account_handler.sql` once manually. New and reset Staff
passwords are stored as one-way hashes; existing demo passwords are upgraded
when their account successfully logs in.

### 4. Run the application

```bash
python app.py
```

Open in browser: **http://127.0.0.1:5000**

## Demo login

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `1234` |
| Staff | `staff` | `1234` |

## Project structure

```
RadiologyQueueManagementSystem-Web/
├── app.py                 # Start Flask server
├── config.py              # Settings from .env
├── init_db.py             # Apply schema.sql to MySQL
├── requirements.txt       # Python dependencies
├── database/
│   └── schema.sql         # MySQL tables + seed data
├── rqms/
│   ├── db.py              # MySQL connection
│   ├── repository.py      # CRUD + LINQ-style queries
│   └── routes.py          # Pages + REST API
├── templates/             # HTML pages
│   ├── index.html         # Login
│   ├── dashboard.html     # Staff dashboard
│   ├── staff_analytics.html  # AHM Staff Analytics
│   ├── results_release.html  # Results Ready for Release
│   └── display.html       # Queue monitor
├── static/
│   ├── css/styles.css     # External stylesheet
│   └── js/
│       ├── api.js         # Fetch calls to Flask API
│       ├── login.js
│       ├── dashboard.js
│       ├── staff_analytics.js
│       ├── results_release.js
│       └── display.js
└── docs/                  # Capstone prototype images
```

## API endpoints (for documentation)

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/` | Login page |
| GET | `/dashboard` | Staff dashboard |
| GET | `/patients` | Registered Patient List |
| GET | `/api/patients/registered` | Read-only list of registered patients |
| GET | `/api/sms/simulation-log` | Recent SMS simulation/audit messages |
| GET | `/display` | Public monitor |
| GET | `/staff-analytics` | AHM Staff Analytics report |
| GET | `/results-release` | Results Ready for Release list |
| GET | `/api/results` | Result release records (filterable) |
| POST | `/api/results/{id}/ready` | Mark ready + optional SMS |
| POST | `/api/results/{id}/released` | Mark claimed/released |
| POST | `/api/results/{id}/notify` | Send result-ready notification |
| GET | `/api/analytics/staff` | Analytics JSON data |
| POST | `/api/login` | Authenticate |
| POST | `/api/logout` | End session |
| GET | `/api/health` | Test MySQL connection |
| GET | `/api/queue/dashboard` | Queue + stats |
| GET | `/api/queue/display` | Queue monitor data + emergency status |
| POST | `/api/queue/emergency` | Activate/deactivate emergency mode and record timestamps |
| POST | `/api/queue/register` | Add patient |
| POST | `/api/queue/reminders` | Process automatic five-patients-ahead reminders |
| POST | `/api/queue/call-next` | Call next |
| POST | `/api/queue/{id}/skip` | Skip |
| POST | `/api/queue/{id}/recall` | Recall |
| POST | `/api/queue/complete` | Complete |

### SIM800C SMS setup

Connect the SIM800C USB GSM module and set its serial port in `.env`:

```
SIM800C_PORT=COM3
SIM800C_BAUDRATE=9600
SIM800C_TIMEOUT=5
SMS_MODE=sim800c
```

The application uses the modem's AT commands and marks a notification as
**Sent** only after the SIM800C confirms the transmission. Set
`SMS_MODE=simulation` in `.env` to record messages without sending anything
over the air; `sim800c` is the default and sends real messages through the
connected modem.
Only patients who enabled SMS at registration receive these notifications.
When staff select **Call Next Patient**, an opted-in patient receives their
queue number and actual assigned room (for example,
`R133, please proceed to Ultrasound Room 1.`). Queue reminders and result-ready
notifications continue to use their existing triggers and SMS preferences.
An opted-in patient receives the five-patients-away reminder when their
position is exactly sixth in the currently waiting queue (five waiting patients
ahead). Called, served, cancelled, and other non-waiting entries are excluded
from the position count. Each queue record is attempted once; failed attempts
are logged and are not retried on subsequent refreshes.
Selecting **Emergency** as a patient's queue priority, or activating Emergency
Mode, sends one notice per emergency incident to currently waiting Regular
patients who opted into SMS and have a valid phone number. Both actions share
the incident's notification marker, so using both does not send duplicate
notices. Notification attempts are recorded in the SMS log; a failed SMS does
not cancel the emergency registration or Emergency Mode activation.
For an existing database, run `database/migration_sms_log.sql` once.

## Thesis software requirements (aligned)

- Windows 10/11  
- Visual Studio Code  
- Python 3  
- MySQL + XAMPP  
- HTML / CSS / JavaScript  
- Google Chrome or Microsoft Edge  

## Legacy static files

Root-level `index.html`, `css/`, `js/` (localStorage version) are kept for reference. **Use Flask** (`python app.py`) as the official capstone system.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Can't connect to MySQL` | Start XAMPP MySQL; check `.env` password |
| `Unknown database rqms_db` | Run `python init_db.py` or import `schema.sql` |
| Login works but queue empty | Re-import seed data in `schema.sql` |
| Port 5000 in use | Change port in `app.py` |
