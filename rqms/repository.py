"""Data access and queue business logic (LINQ-style queries in Python)."""

from datetime import datetime, timedelta

from mysql.connector import Error

from rqms.db import get_connection

QUEUE_STATUS = {
    "WAITING": "Waiting",
    "CALLED": "Called",
    "SERVING": "Serving",
    "COMPLETED": "Completed",
    "SKIPPED": "Skipped",
}

RESULT_STATUS = {
    "NONE": "—",
    "PROCESSING": "Processing",
    "READY": "Ready for Release",
    "RELEASED": "Released",
}

_PATIENT_SELECT = """
    queue_id, queue_number, patient_name, patient_phone, patient_priority,
    sms_enabled, reminder_sent, service_type, assigned_room,
    status, registered_at, called_at, completed_at, tracking_code,
    result_status, result_ready_at, result_released_at, result_notify_sent
"""


def _row_to_patient(row):
    """Map DB row to JSON-friendly dict for the frontend."""
    return {
        "queueId": row["queue_id"],
        "queueNumber": row["queue_number"],
        "patientName": row["patient_name"],
        "patientPhone": row.get("patient_phone") or "",
        "priority": row.get("patient_priority") or "Regular",
        "smsEnabled": bool(row.get("sms_enabled")),
        "reminderSent": bool(row.get("reminder_sent")),
        "serviceType": row["service_type"],
        "assignedRoom": row["assigned_room"],
        "status": row["status"],
        "registeredAt": row["registered_at"].isoformat() if row["registered_at"] else None,
        "calledAt": row["called_at"].isoformat() if row["called_at"] else None,
        "completedAt": row["completed_at"].isoformat() if row["completed_at"] else None,
        "trackingCode": row["tracking_code"],
        "resultStatus": row.get("result_status") or RESULT_STATUS["NONE"],
        "resultReadyAt": row["result_ready_at"].isoformat()
        if row.get("result_ready_at")
        else None,
        "resultReleasedAt": row["result_released_at"].isoformat()
        if row.get("result_released_at")
        else None,
        "resultNotifySent": bool(row.get("result_notify_sent")),
    }


def _normalize_priority(value):
    return value if value in ("Regular", "Priority") else "Regular"


def _queue_sort_key(patient):
    priority_rank = 0 if patient.get("priority") == "Priority" else 1
    return (priority_rank, patient.get("registeredAt") or "")


def try_login(username, password, role):
    """Validate staff credentials."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT user_id, username, full_name, role
            FROM users
            WHERE LOWER(username) = LOWER(%s)
              AND password = %s
              AND LOWER(role) = LOWER(%s)
            """,
            (username, password, role),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "userId": row["user_id"],
            "username": row["username"],
            "fullName": row["full_name"],
            "role": row["role"],
        }
    finally:
        cursor.close()
        conn.close()


def get_all_patients():
    """Read all queue records ordered by registration time."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            f"SELECT {_PATIENT_SELECT} FROM queue_patients ORDER BY registered_at"
        )
        return [_row_to_patient(r) for r in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_active_queue():
    """LINQ-style filter: patients not completed or skipped, ordered by priority."""
    all_patients = get_all_patients()
    active_patients = [
        p
        for p in all_patients
        if p["status"] not in (QUEUE_STATUS["COMPLETED"], QUEUE_STATUS["SKIPPED"])
    ]
    return sorted(active_patients, key=_queue_sort_key)


def get_current_serving():
    """Patient currently called or serving."""
    active = get_active_queue()
    serving = [p for p in active if p["status"] in (QUEUE_STATUS["CALLED"], QUEUE_STATUS["SERVING"])]
    if not serving:
        return None
    serving.sort(
        key=lambda p: p["calledAt"] or p["registeredAt"],
        reverse=True,
    )
    return serving[0]


def get_queue_stats():
    """Aggregate statistics for dashboard cards."""
    all_patients = get_all_patients()
    today = datetime.now().date()

    def is_today(iso_str):
        if not iso_str:
            return False
        return datetime.fromisoformat(iso_str).date() == today

    today_patients = [p for p in all_patients if is_today(p["registeredAt"])]

    return {
        "waitingCount": sum(1 for p in all_patients if p["status"] == QUEUE_STATUS["WAITING"]),
        "servingCount": sum(1 for p in all_patients if p["status"] == QUEUE_STATUS["SERVING"]),
        "completedToday": sum(
            1 for p in today_patients if p["status"] == QUEUE_STATUS["COMPLETED"]
        ),
        "skippedToday": sum(1 for p in today_patients if p["status"] == QUEUE_STATUS["SKIPPED"]),
        "totalToday": len(today_patients),
    }


def get_room_catalog():
    """Return all saved room names ordered for the admin UI and registration form."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT room_id, room_name FROM room_catalog ORDER BY room_name")
        return [{"roomId": row["room_id"], "roomName": row["room_name"]} for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_service_catalog():
    """Return all saved service names ordered for the admin UI and registration form."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT service_id, service_name FROM service_catalog ORDER BY service_name")
        return [{"serviceId": row["service_id"], "serviceName": row["service_name"]} for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def create_or_update_room(room_id, room_name):
    """Create a room or update an existing room name."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if room_id is not None:
            cursor.execute(
                "UPDATE room_catalog SET room_name = %s WHERE room_id = %s",
                (room_name, room_id),
            )
        else:
            cursor.execute(
                "INSERT INTO room_catalog (room_name) VALUES (%s)",
                (room_name,),
            )
        conn.commit()
        return True, None
    except Error as ex:
        return False, str(ex)
    finally:
        cursor.close()
        conn.close()


def create_or_update_service(service_id, service_name):
    """Create a service or update an existing service name."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if service_id is not None:
            cursor.execute(
                "UPDATE service_catalog SET service_name = %s WHERE service_id = %s",
                (service_name, service_id),
            )
        else:
            cursor.execute(
                "INSERT INTO service_catalog (service_name) VALUES (%s)",
                (service_name,),
            )
        conn.commit()
        return True, None
    except Error as ex:
        return False, str(ex)
    finally:
        cursor.close()
        conn.close()


def generate_next_queue_number():
    """Next R-### number based on existing records."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT queue_number FROM queue_patients WHERE queue_number LIKE 'R-%'"
        )
        max_num = 100
        for (num_str,) in cursor.fetchall():
            try:
                n = int(num_str.replace("R-", ""))
                max_num = max(max_num, n)
            except ValueError:
                pass
        return f"R-{max_num + 1}"
    finally:
        cursor.close()
        conn.close()


def get_patient_by_id(queue_id):
    """Find one patient by primary key."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            f"SELECT {_PATIENT_SELECT} FROM queue_patients WHERE queue_id = %s",
            (queue_id,),
        )
        row = cursor.fetchone()
        return _row_to_patient(row) if row else None
    finally:
        cursor.close()
        conn.close()


def register_patient(patient_name, service_type, assigned_room, sms_notify=False, patient_phone=None, patient_priority="Regular"):
    """Create new waiting patient (CRUD — Create)."""
    queue_number = generate_next_queue_number()
    tracking = "TRK-" + queue_number.replace("R-", "")
    now = datetime.now()
    priority_value = _normalize_priority(patient_priority)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO queue_patients
            (queue_number, patient_name, patient_phone, patient_priority, sms_enabled,
             reminder_sent, service_type, assigned_room, status,
             registered_at, tracking_code, result_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                queue_number,
                patient_name,
                patient_phone or None,
                priority_value,
                1 if sms_notify else 0,
                0,
                service_type,
                assigned_room,
                QUEUE_STATUS["WAITING"],
                now,
                tracking,
                RESULT_STATUS["NONE"],
            ),
        )
        conn.commit()
        queue_id = cursor.lastrowid
        patient = get_patient_by_id(queue_id)
        patient["smsQueued"] = sms_notify
        return patient
    finally:
        cursor.close()
        conn.close()


def update_patient(patient):
    """Update queue record (CRUD — Update)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        called = patient.get("calledAt")
        completed = patient.get("completedAt")
        cursor.execute(
            """
            UPDATE queue_patients SET
              queue_number = %s, patient_name = %s, patient_phone = %s,
              patient_priority = %s, sms_enabled = %s, reminder_sent = %s,
              service_type = %s, assigned_room = %s, status = %s,
              registered_at = %s, called_at = %s, completed_at = %s,
              tracking_code = %s, result_status = %s, result_ready_at = %s,
              result_released_at = %s, result_notify_sent = %s
            WHERE queue_id = %s
            """,
            (
                patient["queueNumber"],
                patient["patientName"],
                patient.get("patientPhone") or None,
                _normalize_priority(patient.get("priority", "Regular")),
                1 if patient.get("smsEnabled") else 0,
                1 if patient.get("reminderSent") else 0,
                patient["serviceType"],
                patient["assignedRoom"],
                patient["status"],
                datetime.fromisoformat(patient["registeredAt"]),
                datetime.fromisoformat(called) if called else None,
                datetime.fromisoformat(completed) if completed else None,
                patient["trackingCode"],
                patient.get("resultStatus", RESULT_STATUS["NONE"]),
                datetime.fromisoformat(patient["resultReadyAt"])
                if patient.get("resultReadyAt")
                else None,
                datetime.fromisoformat(patient["resultReleasedAt"])
                if patient.get("resultReleasedAt")
                else None,
                1 if patient.get("resultNotifySent") else 0,
                patient["queueId"],
            ),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def dispatch_pending_reminders():
    """Queue a simulated SMS reminder when a patient is due in the next 10-minute window."""
    waiting_patients = [
        p
        for p in get_active_queue()
        if p["status"] == QUEUE_STATUS["WAITING"]
        and p.get("smsEnabled")
        and p.get("patientPhone")
        and not p.get("reminderSent")
    ]

    now = datetime.now()
    sent = []

    for index, patient in enumerate(waiting_patients):
        registered = datetime.fromisoformat(patient["registeredAt"])
        due_at = registered + timedelta(minutes=index * 10)
        if now < due_at:
            continue

        patient["reminderSent"] = True
        update_patient(patient)
        sent.append(
            {
                "queueNumber": patient["queueNumber"],
                "patientName": patient["patientName"],
                "message": (
                    f"Reminder queued for {patient['queueNumber']} ({patient['patientName']}) "
                    "— patient should be ready in 10 minutes."
                ),
            }
        )

    return sent


def get_reminder_simulation():
    """Return a preview of the next SMS reminder simulation based on queue timing."""
    waiting_patients = [
        p
        for p in get_active_queue()
        if p["status"] == QUEUE_STATUS["WAITING"]
        and p.get("smsEnabled")
        and p.get("patientPhone")
        and not p.get("reminderSent")
    ]

    if not waiting_patients:
        return {
            "available": False,
            "message": "No SMS-enabled waiting patients are available for a reminder simulation.",
        }

    now = datetime.now()
    next_patient = None
    next_minutes = None

    for index, patient in enumerate(waiting_patients):
        registered = datetime.fromisoformat(patient["registeredAt"])
        due_at = registered + timedelta(minutes=index * 10)
        minutes_remaining = max(0, int((due_at - now).total_seconds() // 60))

        if next_patient is None or minutes_remaining < next_minutes:
            next_patient = patient
            next_minutes = minutes_remaining

    if next_patient is None:
        return {
            "available": False,
            "message": "No SMS-enabled waiting patients are available for a reminder simulation.",
        }

    if next_minutes == 0:
        message = (
            f"Simulation: {next_patient['queueNumber']} ({next_patient['patientName']}) is eligible "
            "for a reminder right now."
        )
    else:
        message = (
            f"Simulation: {next_patient['queueNumber']} ({next_patient['patientName']}) would receive "
            f"an SMS in {next_minutes} minute(s)."
        )

    return {
        "available": True,
        "queueNumber": next_patient["queueNumber"],
        "patientName": next_patient["patientName"],
        "serviceType": next_patient["serviceType"],
        "minutesUntilTurn": next_minutes,
        "message": message,
    }


def call_next_patient():
    """Call the next waiting patient; reset other active calls."""
    active = get_active_queue()
    waiting = [p for p in active if p["status"] == QUEUE_STATUS["WAITING"]]
    if not waiting:
        return None, "No waiting patients in queue."

    for p in active:
        if p["status"] in (QUEUE_STATUS["CALLED"], QUEUE_STATUS["SERVING"]):
            p["status"] = QUEUE_STATUS["WAITING"]
            p["calledAt"] = None
            update_patient(p)

    next_p = waiting[0]
    next_p["status"] = QUEUE_STATUS["CALLED"]
    next_p["calledAt"] = datetime.now().isoformat()
    update_patient(next_p)
    return next_p, None


def skip_patient(queue_id):
    patient = get_patient_by_id(queue_id)
    if not patient:
        return None, "Patient not found."
    patient["status"] = QUEUE_STATUS["SKIPPED"]
    update_patient(patient)
    return patient, None


def recall_patient(queue_id):
    patient = get_patient_by_id(queue_id)
    if not patient:
        return None, "Patient not found."
    patient["status"] = QUEUE_STATUS["WAITING"]
    patient["calledAt"] = None
    patient["completedAt"] = None
    update_patient(patient)
    return patient, None


def complete_patient(queue_id=None):
    patient = get_patient_by_id(queue_id) if queue_id else get_current_serving()
    if not patient:
        return None, "Select a patient or call next before completing."
    patient["status"] = QUEUE_STATUS["COMPLETED"]
    now = datetime.now().isoformat()
    patient["completedAt"] = now
    if not patient["calledAt"]:
        patient["calledAt"] = now
    patient["resultStatus"] = RESULT_STATUS["PROCESSING"]
    patient["resultReadyAt"] = None
    patient["resultReleasedAt"] = None
    patient["resultNotifySent"] = False
    update_patient(patient)
    return patient, None


def get_results_list(filter_status=None):
    """
    LINQ-style: completed exams with result release tracking.
    filter_status: Processing | Ready for Release | Released | None (all)
    """
    all_patients = get_all_patients()
    completed = [p for p in all_patients if p["status"] == QUEUE_STATUS["COMPLETED"]]

    if filter_status and filter_status != "All":
        completed = [p for p in completed if p["resultStatus"] == filter_status]

    completed.sort(
        key=lambda p: p["resultReadyAt"] or p["completedAt"] or p["registeredAt"],
        reverse=True,
    )

    ready_count = sum(
        1 for p in all_patients
        if p["status"] == QUEUE_STATUS["COMPLETED"]
        and p["resultStatus"] == RESULT_STATUS["READY"]
    )
    processing_count = sum(
        1 for p in all_patients
        if p["status"] == QUEUE_STATUS["COMPLETED"]
        and p["resultStatus"] == RESULT_STATUS["PROCESSING"]
    )
    released_count = sum(
        1 for p in all_patients
        if p["status"] == QUEUE_STATUS["COMPLETED"]
        and p["resultStatus"] == RESULT_STATUS["RELEASED"]
    )

    return {
        "results": completed,
        "counts": {
            "readyForRelease": ready_count,
            "processing": processing_count,
            "released": released_count,
            "total": len([p for p in all_patients if p["status"] == QUEUE_STATUS["COMPLETED"]]),
        },
    }


def mark_ready_for_release(queue_id, send_notification=True):
    """Mark radiology result ready for patient collection."""
    patient = get_patient_by_id(queue_id)
    if not patient:
        return None, "Patient not found."
    if patient["status"] != QUEUE_STATUS["COMPLETED"]:
        return None, "Exam must be completed before marking results ready."

    now = datetime.now().isoformat()
    patient["resultStatus"] = RESULT_STATUS["READY"]
    patient["resultReadyAt"] = now
    if send_notification:
        patient["resultNotifySent"] = True
    update_patient(patient)

    message = (
        f"SMS to patient: St. Paul Hospital — Your radiology results for "
        f"{patient['queueNumber']} ({patient['serviceType']}) are ready for release. "
        f"Please proceed to the Radiology Release Counter to claim your results."
        if send_notification
        else None
    )
    return patient, message


def mark_result_released(queue_id):
    """Record that the patient claimed / released their results."""
    patient = get_patient_by_id(queue_id)
    if not patient:
        return None, "Patient not found."
    if patient["resultStatus"] != RESULT_STATUS["READY"]:
        return None, "Results must be 'Ready for Release' before marking as released."

    patient["resultStatus"] = RESULT_STATUS["RELEASED"]
    patient["resultReleasedAt"] = datetime.now().isoformat()
    update_patient(patient)
    return patient, None


def send_result_notification(queue_id):
    """Send (simulate) patient notification that results are ready."""
    patient = get_patient_by_id(queue_id)
    if not patient:
        return None, "Patient not found."
    if patient["resultStatus"] != RESULT_STATUS["READY"]:
        return None, "Mark results as 'Ready for Release' first."

    patient["resultNotifySent"] = True
    update_patient(patient)
    msg = (
        f"St. Paul Hospital: Dear {patient['patientName']}, your radiology results "
        f"({patient['queueNumber']}) are ready for claiming at the Release Counter."
    )
    return patient, msg


def get_staff_analytics():
    """
    Staff analytics report — LINQ-style aggregations on queue data.
    Used by the AHM Staff Analytics page for admin and staff oversight.
    """
    all_patients = get_all_patients()
    today = datetime.now().date()

    def is_today(iso_str):
        if not iso_str:
            return False
        return datetime.fromisoformat(iso_str).date() == today

    today_patients = [p for p in all_patients if is_today(p["registeredAt"])]

    # LINQ-style: average wait minutes (registered → called) for completed today
    wait_minutes = []
    for p in today_patients:
        if p["calledAt"] and p["registeredAt"]:
            reg = datetime.fromisoformat(p["registeredAt"])
            called = datetime.fromisoformat(p["calledAt"])
            wait_minutes.append((called - reg).total_seconds() / 60)

    avg_wait = round(sum(wait_minutes) / len(wait_minutes), 1) if wait_minutes else 0

    completed_today = [p for p in today_patients if p["status"] == QUEUE_STATUS["COMPLETED"]]
    skipped_today = [p for p in today_patients if p["status"] == QUEUE_STATUS["SKIPPED"]]
    total_today = len(today_patients)

    completion_rate = (
        round(len(completed_today) / total_today * 100, 1) if total_today > 0 else 0
    )

    # LINQ-style: group by service type
    service_groups = {}
    for p in today_patients:
        service_groups[p["serviceType"]] = service_groups.get(p["serviceType"], 0) + 1
    by_service = [
        {"label": k, "count": v}
        for k, v in sorted(service_groups.items(), key=lambda x: -x[1])
    ]

    # LINQ-style: group by room
    room_groups = {}
    for p in today_patients:
        room_groups[p["assignedRoom"]] = room_groups.get(p["assignedRoom"], 0) + 1
    by_room = [
        {"label": k, "count": v}
        for k, v in sorted(room_groups.items(), key=lambda x: -x[1])
    ]

    # LINQ-style: group by status (all records)
    status_groups = {}
    for p in all_patients:
        status_groups[p["status"]] = status_groups.get(p["status"], 0) + 1
    by_status = [{"label": k, "count": v} for k, v in status_groups.items()]

    # Hourly volume today (registrations per hour)
    hourly = {h: 0 for h in range(8, 18)}
    for p in today_patients:
        hour = datetime.fromisoformat(p["registeredAt"]).hour
        if hour in hourly:
            hourly[hour] += 1
    hourly_volume = [{"hour": f"{h}:00", "count": hourly[h]} for h in sorted(hourly)]

    # Recent completed (newest first)
    recent_completed = sorted(
        completed_today,
        key=lambda p: p["completedAt"] or p["registeredAt"],
        reverse=True,
    )[:10]

    return {
        "reportDate": today.isoformat(),
        "summary": {
            "totalToday": total_today,
            "completedToday": len(completed_today),
            "skippedToday": len(skipped_today),
            "waitingNow": sum(1 for p in all_patients if p["status"] == QUEUE_STATUS["WAITING"]),
            "activeNow": len(get_active_queue()),
            "avgWaitMinutes": avg_wait,
            "completionRate": completion_rate,
        },
        "byService": by_service,
        "byRoom": by_room,
        "byStatus": by_status,
        "hourlyVolume": hourly_volume,
        "recentCompleted": recent_completed,
    }
