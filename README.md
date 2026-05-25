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
| POST | `/api/queue/register` | Add patient |
| POST | `/api/queue/call-next` | Call next |
| POST | `/api/queue/{id}/skip` | Skip |
| POST | `/api/queue/{id}/recall` | Recall |
| POST | `/api/queue/complete` | Complete |

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
