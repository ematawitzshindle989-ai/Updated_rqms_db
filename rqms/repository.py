"""Data access and queue business logic (LINQ-style queries in Python)."""

from datetime import datetime

from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash

from rqms.db import get_connection
from rqms.sms import SmsError, send_sms, validate_phone_number

QUEUE_STATUS = {
    "WAITING": "Waiting",
    "CALLED": "Called",
    "SERVING": "Serving",
    "COMPLETED": "Completed",
    "SKIPPED": "Skipped",
    "CANCELLED": "Cancelled",
}

REMINDER_AHEAD_COUNT = 5

RESULT_STATUS = {
    "NONE": "—",
    "PROCESSING": "Processing",
    "READY": "Ready for Release",
    "RELEASED": "Released",
}

_PATIENT_SELECT = """
    queue_id, queue_number, patient_name, patient_phone, patient_priority,
    sms_enabled, reminder_sent, service_type, assigned_room,
    reminder_status, reminder_sent_at,
    status, registered_at, called_at, completed_at, tracking_code,
    result_status, result_ready_at, result_released_at, result_notify_sent,
    turn_notification_status, turn_notification_sent_at
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
        "reminderStatus": row.get("reminder_status") or ("Sent" if row.get("reminder_sent") else "Not Sent"),
        "reminderSentAt": row["reminder_sent_at"].isoformat()
        if row.get("reminder_sent_at")
        else None,
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
        "turnNotificationStatus": row.get("turn_notification_status")
        or ("Sent" if row.get("result_notify_sent") else "Not Sent"),
        "turnNotificationSentAt": row["turn_notification_sent_at"].isoformat()
        if row.get("turn_notification_sent_at")
        else None,
    }


def _normalize_priority(value):
    return value if value in ("Regular", "Priority", "Emergency") else "Regular"


def _queue_sort_key(patient):
    priority_rank = {
        "Emergency": 0,
        "Priority": 1,
        "Regular": 2,
    }.get(patient.get("priority"), 2)
    return (priority_rank, patient.get("registeredAt") or "")


def try_login(username, password, role):
    """Validate staff credentials."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT user_id, username, password, full_name, role, is_active
            FROM users
            WHERE LOWER(username) = LOWER(%s)
              AND LOWER(role) = LOWER(%s)
            """,
            (username, role),
        )
        row = cursor.fetchone()
        if not row or not row["is_active"]:
            return None

        stored_password = row["password"]
        if stored_password.startswith(("pbkdf2:", "scrypt:")):
            valid_password = check_password_hash(stored_password, password)
        else:
            valid_password = stored_password == password
            if valid_password:
                cursor.execute(
                    """
                    UPDATE users SET password = %s
                    WHERE user_id = %s AND password = %s
                    """,
                    (generate_password_hash(password), row["user_id"], stored_password),
                )
                conn.commit()

        if not valid_password:
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


def is_account_active(user_id):
    """Check active state for a logged-in account before serving protected routes."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT is_active FROM users WHERE user_id = %s",
            (user_id,),
        )
        row = cursor.fetchone()
        return bool(row and row[0])
    finally:
        cursor.close()
        conn.close()


def get_staff_accounts():
    """Return account-management fields for Staff accounts only."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT user_id, username, full_name, is_active
            FROM users
            WHERE role = 'Staff'
            ORDER BY full_name, username
            """
        )
        return [
            {
                "userId": row["user_id"],
                "username": row["username"],
                "fullName": row["full_name"],
                "isActive": bool(row["is_active"]),
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()
        conn.close()


def create_staff_account(username, password, full_name):
    """Create a Staff account with a one-way password hash."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (username, password, full_name, role, is_active)
            VALUES (%s, %s, %s, 'Staff', 1)
            """,
            (username, generate_password_hash(password), full_name),
        )
        conn.commit()
        return cursor.lastrowid
    except Error as exc:
        if exc.errno == 1062:
            return None
        raise
    finally:
        cursor.close()
        conn.close()


def update_staff_account(user_id, username, full_name):
    """Update the username and display name of a Staff account."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET username = %s, full_name = %s
            WHERE user_id = %s AND role = 'Staff'
            """,
            (username, full_name, user_id),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return True
        cursor.execute(
            "SELECT 1 FROM users WHERE user_id = %s AND role = 'Staff'",
            (user_id,),
        )
        return cursor.fetchone() is not None
    except Error as exc:
        if exc.errno == 1062:
            return None
        raise
    finally:
        cursor.close()
        conn.close()


def reset_staff_password(user_id, password):
    """Set a new one-way password hash for a Staff account."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users SET password = %s
            WHERE user_id = %s AND role = 'Staff'
            """,
            (generate_password_hash(password), user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def set_staff_account_active(user_id, is_active):
    """Activate or deactivate a Staff account."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users SET is_active = %s
            WHERE user_id = %s AND role = 'Staff'
            """,
            (1 if is_active else 0, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def delete_staff_account(user_id):
    """Delete a Staff account without allowing Admin accounts to be targeted."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM users WHERE user_id = %s AND role = 'Staff'",
            (user_id,),
        )
        if cursor.fetchone() is None:
            return False
        cursor.execute(
            """
            UPDATE emergency_cases
            SET activated_by = CASE WHEN activated_by = %s THEN NULL ELSE activated_by END,
                deactivated_by = CASE WHEN deactivated_by = %s THEN NULL ELSE deactivated_by END
            WHERE activated_by = %s OR deactivated_by = %s
            """,
            (user_id, user_id, user_id, user_id),
        )
        cursor.execute(
            "DELETE FROM users WHERE user_id = %s AND role = 'Staff'",
            (user_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
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
    """Return patients still occupying a position in the active queue."""
    all_patients = get_all_patients()
    active_patients = [
        p
        for p in all_patients
        if p["status"] not in (
            QUEUE_STATUS["COMPLETED"],
            QUEUE_STATUS["SKIPPED"],
            QUEUE_STATUS["CANCELLED"],
        )
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


def get_emergency_status():
    """Return the current emergency state and its audit timestamps."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT emergency_id, activated_at, deactivated_at
            FROM emergency_cases
            ORDER BY emergency_id DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return {"active": False, "activatedAt": None, "deactivatedAt": None}
        return {
            "active": row["deactivated_at"] is None,
            "emergencyId": row["emergency_id"],
            "activatedAt": row["activated_at"].isoformat() if row["activated_at"] else None,
            "deactivatedAt": row["deactivated_at"].isoformat() if row["deactivated_at"] else None,
        }
    finally:
        cursor.close()
        conn.close()


def activate_emergency(user_id):
    """Start an emergency unless one is already active."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT emergency_id
            FROM emergency_cases
            WHERE deactivated_at IS NULL
            ORDER BY emergency_id DESC
            LIMIT 1
            """
        )
        if cursor.fetchone():
            return get_emergency_status(), False
        cursor.execute(
            """
            INSERT INTO emergency_cases (activated_at, activated_by, sms_notification_started_at)
            VALUES (%s, %s, NULL)
            """,
            (datetime.now(), user_id),
        )
        conn.commit()
        return get_emergency_status(), True
    finally:
        cursor.close()
        conn.close()


def deactivate_emergency(user_id):
    """End the active emergency and preserve its activation history."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT emergency_id
            FROM emergency_cases
            WHERE deactivated_at IS NULL
            ORDER BY emergency_id DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return get_emergency_status(), False
        cursor.execute(
            """
            UPDATE emergency_cases
            SET deactivated_at = %s, deactivated_by = %s
            WHERE emergency_id = %s
            """,
            (datetime.now(), user_id, row["emergency_id"]),
        )
        conn.commit()
        return get_emergency_status(), True
    finally:
        cursor.close()
        conn.close()


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
              reminder_status = %s, reminder_sent_at = %s,
              service_type = %s, assigned_room = %s, status = %s,
              registered_at = %s, called_at = %s, completed_at = %s,
              tracking_code = %s, result_status = %s, result_ready_at = %s,
              result_released_at = %s, result_notify_sent = %s,
              turn_notification_status = %s, turn_notification_sent_at = %s
            WHERE queue_id = %s
            """,
            (
                patient["queueNumber"],
                patient["patientName"],
                patient.get("patientPhone") or None,
                _normalize_priority(patient.get("priority", "Regular")),
                1 if patient.get("smsEnabled") else 0,
                1 if patient.get("reminderSent") else 0,
                patient.get("reminderStatus", "Not Sent"),
                datetime.fromisoformat(patient["reminderSentAt"])
                if patient.get("reminderSentAt")
                else None,
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
                patient.get("turnNotificationStatus", "Not Sent"),
                datetime.fromisoformat(patient["turnNotificationSentAt"])
                if patient.get("turnNotificationSentAt")
                else None,
                patient["queueId"],
            ),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def record_sms_log(patient, notification_type, message, status):
    """Persist each SMS attempt for simulation and future modem auditing."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO sms_notification_log
              (queue_id, patient_name, recipient, notification_type, message, status, sent_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                patient["queueId"],
                patient["patientName"],
                patient["patientPhone"],
                notification_type,
                message,
                status,
                datetime.now(),
            ),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


EMERGENCY_QUEUE_MESSAGE = (
    "ST. PAUL HOSPITAL - RADIOLOGY\n\n"
    "Emergency case prioritized. Please be advised that the queue may be delayed. "
    "We appreciate your patience."
)


def send_emergency_queue_notice(emergency_id):
    """Send one emergency notice to eligible waiting regular patients per incident."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE emergency_cases
            SET sms_notification_started_at = %s
            WHERE emergency_id = %s AND sms_notification_started_at IS NULL
            """,
            (datetime.now(), emergency_id),
        )
        if cursor.rowcount != 1:
            return {
                "status": "skipped",
                "sent": 0,
                "failed": 0,
                "skipped": 0,
                "failures": [],
                "message": "Emergency notice was already attempted for this incident.",
            }
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    result = {
        "status": "sent",
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "failures": [],
        "message": "",
    }
    try:
        waiting_regular = [
            patient
            for patient in get_active_queue()
            if patient["status"] == QUEUE_STATUS["WAITING"]
            and patient.get("priority", "Regular") == "Regular"
        ]
    except Error as exc:
        result.update(
            {
                "status": "failed",
                "message": "Could not load waiting patients: " + str(exc),
            }
        )
        return result

    for patient in waiting_regular:
        if not patient.get("smsEnabled") or not patient.get("patientPhone"):
            result["skipped"] += 1
            continue
        try:
            recipient = validate_phone_number(patient["patientPhone"])
        except SmsError:
            result["skipped"] += 1
            continue

        try:
            delivery_status = send_sms(recipient, EMERGENCY_QUEUE_MESSAGE)
        except SmsError as exc:
            result["failed"] += 1
            result["failures"].append(
                {"queueNumber": patient["queueNumber"], "message": str(exc)}
            )
            try:
                record_sms_log(
                    patient,
                    "Emergency Queue Notice",
                    EMERGENCY_QUEUE_MESSAGE,
                    "Failed",
                )
            except Error as log_error:
                result["failures"][-1]["message"] += (
                    " SMS log could not be saved: " + str(log_error)
                )
            continue

        result["sent"] += 1
        try:
            record_sms_log(
                patient,
                "Emergency Queue Notice",
                EMERGENCY_QUEUE_MESSAGE,
                delivery_status,
            )
        except Error as log_error:
            result["failures"].append(
                {
                    "queueNumber": patient["queueNumber"],
                    "message": "SMS was sent, but its log could not be saved: "
                    + str(log_error),
                }
            )

    if result["failed"] or result["failures"]:
        result["status"] = "partial" if result["sent"] else "failed"
        result["message"] = "Some emergency SMS notifications failed."
    elif not result["sent"]:
        result["status"] = "skipped"
        result["message"] = "No eligible waiting regular patients were found."
    else:
        result["message"] = "Emergency notice sent to waiting patients."
    return result


def get_sms_notification_log(limit=50):
    """Return recent SMS attempts for the staff simulation/audit panel."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT sms_log_id, queue_id, patient_name, recipient,
                   notification_type, message, status, sent_at
            FROM sms_notification_log
            ORDER BY sent_at DESC, sms_log_id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [
            {
                "logId": row["sms_log_id"],
                "queueId": row["queue_id"],
                "patientName": row["patient_name"],
                "recipient": row["recipient"],
                "notificationType": row["notification_type"],
                "message": row["message"],
                "status": row["status"],
                "sentAt": row["sent_at"].isoformat() if row["sent_at"] else None,
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()
        conn.close()


def dispatch_pending_reminders():
    """Send the one-time reminder to an eligible fifth waiting patient."""
    active_queue = get_active_queue()
    waiting_queue = [
        patient
        for patient in active_queue
        if patient["status"] == QUEUE_STATUS["WAITING"]
    ]
    results = []

    for index, patient in enumerate(waiting_queue):
        if index != REMINDER_AHEAD_COUNT:
            continue
        if (
            not patient.get("smsEnabled")
            or not patient.get("patientPhone")
            or patient.get("reminderSent")
            or patient.get("reminderStatus")
            in ("Sent", "Simulation Sent", "Sending", "Failed")
        ):
            continue
        try:
            phone = validate_phone_number(patient["patientPhone"])
        except SmsError:
            continue
        if not _claim_queue_reminder(patient["queueId"]):
            continue

        patient["reminderStatus"] = "Sending"
        message = (
            "ST. PAUL HOSPITAL - RADIOLOGY\n\n"
            f"{patient['queueNumber']}, you are {REMINDER_AHEAD_COUNT} patients away "
            "from your turn. Please be ready and stay near the designated area."
        )
        try:
            delivery_status = send_sms(phone, message)
        except SmsError as exc:
            patient["reminderStatus"] = "Failed"
            patient["reminderSent"] = False
            update_patient(patient)
            record_sms_log(patient, "Queue Reminder", message, "Failed")
            results.append(
                {
                    "queueNumber": patient["queueNumber"],
                    "message": "5-patients-away SMS failed: " + str(exc),
                    "failed": True,
                }
            )
            continue
        patient["reminderSent"] = True
        patient["reminderStatus"] = delivery_status
        patient["reminderSentAt"] = datetime.now().isoformat()
        update_patient(patient)
        record_sms_log(patient, "Queue Reminder", message, delivery_status)
        results.append(
            {
                "queueNumber": patient["queueNumber"],
                "message": message,
                "failed": False,
            }
        )

    return results


def _claim_queue_reminder(queue_id):
    """Atomically reserve a reminder attempt so concurrent refreshes cannot duplicate it."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE queue_patients
            SET reminder_status = 'Sending'
            WHERE queue_id = %s
              AND status = %s
              AND sms_enabled = 1
              AND reminder_sent = 0
              AND COALESCE(reminder_status, 'Not Sent')
                  NOT IN ('Sent', 'Simulation Sent', 'Sending', 'Failed')
            """,
            (queue_id, QUEUE_STATUS["WAITING"]),
        )
        claimed = cursor.rowcount == 1
        if claimed:
            conn.commit()
        return claimed
    finally:
        cursor.close()
        conn.close()


def get_reminder_simulation():
    """Return a preview of the patient currently five active positions away."""
    waiting_queue = [
        patient
        for patient in get_active_queue()
        if patient["status"] == QUEUE_STATUS["WAITING"]
    ]
    candidates = []
    if len(waiting_queue) > REMINDER_AHEAD_COUNT:
        patient = waiting_queue[REMINDER_AHEAD_COUNT]
        if (
            patient.get("smsEnabled")
            and patient.get("patientPhone")
            and not patient.get("reminderSent")
            and patient.get("reminderStatus")
            not in ("Sent", "Simulation Sent", "Sending", "Failed")
        ):
            try:
                validate_phone_number(patient["patientPhone"])
            except SmsError:
                pass
            else:
                candidates.append(patient)
    next_patient = candidates[0] if candidates else None

    if not next_patient:
        return {
            "available": False,
            "message": "No eligible SMS-enabled patient is currently five waiting positions away.",
        }

    message = (
        f"Simulation: {next_patient['queueNumber']} is exactly {REMINDER_AHEAD_COUNT} "
        "waiting patients away from their turn."
    )

    return {
        "available": True,
        "queueNumber": next_patient["queueNumber"],
        "patientName": next_patient["patientName"],
        "serviceType": next_patient["serviceType"],
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


def send_call_notification(patient):
    """Send an opted-in patient their queue number and assigned room."""
    if not patient.get("smsEnabled"):
        return {"status": "Skipped", "message": "SMS notification is not enabled."}
    if not patient.get("patientPhone"):
        return {"status": "Failed", "message": "Patient phone number is missing."}

    message = (
        f"{patient['queueNumber']}, please proceed to {patient['assignedRoom']}."
    )
    try:
        delivery_status = send_sms(patient["patientPhone"], message)
    except SmsError as exc:
        record_sms_log(patient, "Patient Called", message, "Failed")
        return {"status": "Failed", "message": str(exc)}

    record_sms_log(patient, "Patient Called", message, delivery_status)
    return {"status": delivery_status, "message": message}


def skip_patient(queue_id):
    patient = get_patient_by_id(queue_id)
    if not patient:
        return None, "Patient not found."
    patient["status"] = QUEUE_STATUS["SKIPPED"]
    update_patient(patient)
    return patient, None


def cancel_patient(queue_id):
    patient = get_patient_by_id(queue_id)
    if not patient:
        return None, "Patient not found."
    if patient["status"] in (QUEUE_STATUS["COMPLETED"], QUEUE_STATUS["SKIPPED"]):
        return None, "This queue entry cannot be cancelled."
    patient["status"] = "Cancelled"
    update_patient(patient)
    return patient, None


def move_patient(queue_id, direction):
    """Move a waiting patient by swapping registration order with its neighbor."""
    patients = [
        p for p in get_active_queue()
        if p["status"] == QUEUE_STATUS["WAITING"]
    ]
    index = next((i for i, p in enumerate(patients) if p["queueId"] == queue_id), None)
    if index is None:
        return None, "Only waiting patients can be moved."
    neighbor_index = index - 1 if direction == "up" else index + 1
    if neighbor_index < 0 or neighbor_index >= len(patients):
        return patients[index], None

    current = patients[index]
    neighbor = patients[neighbor_index]
    current_registered = current["registeredAt"]
    current["registeredAt"] = neighbor["registeredAt"]
    neighbor["registeredAt"] = current_registered
    update_patient(current)
    update_patient(neighbor)
    return current, None


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
    update_patient(patient)
    return patient, None


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
    """Send the manual turn notification through SIM800C once."""
    patient = get_patient_by_id(queue_id)
    if not patient:
        return None, "Patient not found."
    if patient["resultStatus"] != RESULT_STATUS["READY"]:
        return None, "Mark results as 'Ready for Release' first."
    if not patient["smsEnabled"]:
        return None, "SMS notification is not enabled for this patient."
    if patient.get("turnNotificationStatus") in ("Sent", "Simulation Sent"):
        return None, "The turn notification has already been sent."

    patient["turnNotificationStatus"] = "Sending"
    update_patient(patient)
    msg = (
        f"YOUR TURN: Queue number {patient['queueNumber']} is now ready. "
        "Please proceed to the designated counter. Thank you."
    )
    try:
        delivery_status = send_sms(patient["patientPhone"], msg)
    except SmsError as exc:
        patient["turnNotificationStatus"] = "Failed"
        update_patient(patient)
        record_sms_log(patient, "Turn Notification", msg, "Failed")
        return None, str(exc)
    patient["resultNotifySent"] = True
    patient["turnNotificationStatus"] = delivery_status
    patient["turnNotificationSentAt"] = datetime.now().isoformat()
    update_patient(patient)
    record_sms_log(patient, "Turn Notification", msg, delivery_status)
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

    completed_today_cohort = [
        p for p in today_patients if p["status"] == QUEUE_STATUS["COMPLETED"]
    ]
    completed_today = [
        p
        for p in all_patients
        if p["status"] == QUEUE_STATUS["COMPLETED"] and is_today(p["completedAt"])
    ]
    skipped_today = [p for p in today_patients if p["status"] == QUEUE_STATUS["SKIPPED"]]
    total_today = len(today_patients)

    completion_rate = (
        round(len(completed_today_cohort) / total_today * 100, 1)
        if total_today > 0
        else 0
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

    # Recent completed today (newest first).
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
