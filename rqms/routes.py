"""Web pages and REST API routes."""

import re
from functools import wraps

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for
from mysql.connector import Error

from config import Config
from rqms import repository
from rqms.db import test_connection
from rqms.sms import SmsError, validate_phone_number

bp = Blueprint("rqms", __name__)


def login_required_page(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("rqms.login_page"))
        if not repository.is_account_active(session["user"]["userId"]):
            session.clear()
            return redirect(url_for("rqms.login_page"))
        return f(*args, **kwargs)

    return wrapped


def admin_required_page(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("rqms.login_page"))
        if not repository.is_account_active(session["user"]["userId"]):
            session.clear()
            return redirect(url_for("rqms.login_page"))
        if session["user"].get("role") != "Admin":
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def login_required_api(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "message": "Not authenticated."}), 401
        if not repository.is_account_active(session["user"]["userId"]):
            session.clear()
            return jsonify({"success": False, "message": "Account is inactive."}), 401
        return f(*args, **kwargs)

    return wrapped


def admin_required_api(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "message": "Not authenticated."}), 401
        if not repository.is_account_active(session["user"]["userId"]):
            session.clear()
            return jsonify({"success": False, "message": "Account is inactive."}), 401
        if session["user"].get("role") != "Admin":
            return jsonify({"success": False, "message": "Admin access required."}), 403
        return f(*args, **kwargs)

    return wrapped


# ----- Pages -----


@bp.route("/")
def login_page():
    if "user" in session:
        return redirect(url_for("rqms.dashboard_page"))
    return render_template("index.html")


@bp.route("/dashboard")
@login_required_page
def dashboard_page():
    return render_template("dashboard.html", user=session["user"])


@bp.route("/patients")
@login_required_page
def patients_page():
    return render_template("patients.html", user=session["user"])


@bp.route("/display")
def display_page():
    return render_template("display.html")


@bp.route("/staff-analytics")
@login_required_page
def staff_analytics_page():
    """AHM Staff Analytics — queue performance and volume reports."""
    return render_template("staff_analytics.html", user=session["user"])


@bp.route("/results-release")
@login_required_page
def results_release_page():
    """Results Ready for Release — manage result claiming and notifications."""
    return render_template("results_release.html", user=session["user"])


@bp.route("/account-handler")
@admin_required_page
def account_handler_page():
    """Admin-only Staff account management."""
    return render_template("account_handler.html", user=session["user"])


# ----- Auth API -----


@bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "A valid JSON object is required."}), 400

    username = data.get("username")
    password = data.get("password")
    role = data.get("role")
    if not isinstance(username, str) or not isinstance(password, str) or not isinstance(role, str):
        return jsonify({"success": False, "message": "All fields are required."}), 400
    username = username.strip()

    if not username or not password or not role:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    user = repository.try_login(username, password, role)
    if not user:
        return jsonify({"success": False, "message": "Invalid username, password, or role."}), 401

    session["user"] = user
    return jsonify({"success": True, "message": "Login successful.", "user": user})


@bp.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@bp.route("/api/session")
def api_session():
    if "user" not in session:
        return jsonify({"authenticated": False})
    if not repository.is_account_active(session["user"]["userId"]):
        session.clear()
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": session["user"]})


# ----- Database API -----


@bp.route("/api/health")
def api_health():
    ok, message = test_connection()
    return jsonify({"connected": ok, "message": message})


@bp.route("/api/admin/config")
@login_required_api
def api_admin_config():
    return jsonify(
        {
            "rooms": repository.get_room_catalog(),
            "services": repository.get_service_catalog(),
        }
    )


@bp.route("/api/admin/config/rooms", methods=["POST"])
@admin_required_api
def api_admin_rooms():
    data = request.get_json() or {}
    room_name = (data.get("roomName") or "").strip()
    room_id = data.get("roomId")

    if not room_name:
        return jsonify({"success": False, "message": "Room name is required."}), 400

    if room_id not in (None, ""):
        try:
            room_id = int(room_id)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Invalid room id."}), 400

    ok, error = repository.create_or_update_room(room_id, room_name)
    if not ok:
        return jsonify({"success": False, "message": error}), 400

    return jsonify({"success": True, "rooms": repository.get_room_catalog()})


@bp.route("/api/admin/config/services", methods=["POST"])
@admin_required_api
def api_admin_services():
    data = request.get_json() or {}
    service_name = (data.get("serviceName") or "").strip()
    service_id = data.get("serviceId")

    if not service_name:
        return jsonify({"success": False, "message": "Service name is required."}), 400

    if service_id not in (None, ""):
        try:
            service_id = int(service_id)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Invalid service id."}), 400

    ok, error = repository.create_or_update_service(service_id, service_name)
    if not ok:
        return jsonify({"success": False, "message": error}), 400

    return jsonify({"success": True, "services": repository.get_service_catalog()})


def _staff_account_fields(data, require_password=False):
    if not isinstance(data, dict):
        return None, "A valid JSON object is required."

    username = data.get("username")
    full_name = data.get("fullName")
    password = data.get("password") if require_password else None

    if not isinstance(username, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]{3,50}", username.strip()
    ):
        return None, "Username must be 3-50 characters using letters, numbers, dots, underscores, or hyphens."
    if not isinstance(full_name, str) or not full_name.strip() or len(full_name.strip()) > 100:
        return None, "Full name is required and must be 100 characters or fewer."
    if require_password and (
        not isinstance(password, str) or len(password) < 8 or len(password) > 128
    ):
        return None, "Password must be between 8 and 128 characters."

    return {
        "username": username.strip(),
        "fullName": full_name.strip(),
        "password": password,
    }, None


@bp.route("/api/admin/staff", methods=["GET"])
@admin_required_api
def api_admin_staff_list():
    return jsonify({"staff": repository.get_staff_accounts()})


@bp.route("/api/admin/staff", methods=["POST"])
@admin_required_api
def api_admin_staff_create():
    fields, error = _staff_account_fields(request.get_json(silent=True), require_password=True)
    if error:
        return jsonify({"success": False, "message": error}), 400

    user_id = repository.create_staff_account(
        fields["username"], fields["password"], fields["fullName"]
    )
    if user_id is None:
        return jsonify({"success": False, "message": "That username is already in use."}), 409
    return jsonify({"success": True, "userId": user_id}), 201


@bp.route("/api/admin/staff/<int:user_id>", methods=["PUT"])
@admin_required_api
def api_admin_staff_update(user_id):
    fields, error = _staff_account_fields(request.get_json(silent=True))
    if error:
        return jsonify({"success": False, "message": error}), 400

    updated = repository.update_staff_account(
        user_id, fields["username"], fields["fullName"]
    )
    if updated is None:
        return jsonify({"success": False, "message": "That username is already in use."}), 409
    if not updated:
        return jsonify({"success": False, "message": "Staff account not found."}), 404
    return jsonify({"success": True})


@bp.route("/api/admin/staff/<int:user_id>/password", methods=["POST"])
@admin_required_api
def api_admin_staff_password(user_id):
    data = request.get_json(silent=True)
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        return jsonify(
            {"success": False, "message": "Password must be between 8 and 128 characters."}
        ), 400
    if not repository.reset_staff_password(user_id, password):
        return jsonify({"success": False, "message": "Staff account not found."}), 404
    return jsonify({"success": True})


@bp.route("/api/admin/staff/<int:user_id>/status", methods=["PATCH"])
@admin_required_api
def api_admin_staff_status(user_id):
    data = request.get_json(silent=True)
    is_active = data.get("isActive") if isinstance(data, dict) else None
    if not isinstance(is_active, bool):
        return jsonify({"success": False, "message": "isActive must be true or false."}), 400
    if not repository.set_staff_account_active(user_id, is_active):
        return jsonify({"success": False, "message": "Staff account not found."}), 404
    return jsonify({"success": True})


@bp.route("/api/admin/staff/<int:user_id>", methods=["DELETE"])
@admin_required_api
def api_admin_staff_delete(user_id):
    if not repository.delete_staff_account(user_id):
        return jsonify({"success": False, "message": "Staff account not found."}), 404
    return jsonify({"success": True})


# ----- Queue API -----


@bp.route("/api/queue/dashboard")
@login_required_api
def api_dashboard():
    return jsonify(
        {
            "activeQueue": repository.get_active_queue(),
            "stats": repository.get_queue_stats(),
            "current": repository.get_current_serving(),
            "emergency": repository.get_emergency_status(),
        }
    )


@bp.route("/api/patients/registered")
@login_required_api
def api_registered_patients():
    repository.dispatch_pending_reminders()
    return jsonify({"patients": repository.get_all_patients()})


@bp.route("/api/sms/simulation-log")
@login_required_api
def api_sms_simulation_log():
    repository.dispatch_pending_reminders()
    return jsonify(
        {
            "simulationMode": Config.SMS_MODE == "simulation",
            "logs": repository.get_sms_notification_log(),
        }
    )


@bp.route("/api/queue/display")
def api_display():
    repository.dispatch_pending_reminders()
    return jsonify(
        {
            "current": repository.get_current_serving(),
            "emergency": repository.get_emergency_status(),
            "upcoming": [
                p
                for p in repository.get_active_queue()
                if p["status"] == repository.QUEUE_STATUS["WAITING"]
            ][:6],
        }
    )


@bp.route("/api/queue/emergency", methods=["POST"])
@login_required_api
def api_emergency():
    user_id = session["user"].get("userId")
    data = request.get_json() or {}
    active = data.get("active")
    if not isinstance(active, bool):
        return jsonify({"success": False, "message": "Emergency state must be a boolean."}), 400

    emergency, changed = (
        repository.activate_emergency(user_id)
        if active
        else repository.deactivate_emergency(user_id)
    )
    sms_notification = None
    if active and changed and emergency.get("emergencyId"):
        try:
            sms_notification = repository.send_emergency_queue_notice(
                emergency["emergencyId"]
            )
        except Error as exc:
            sms_notification = {
                "status": "failed",
                "sent": 0,
                "failed": 0,
                "skipped": 0,
                "failures": [],
                "message": "Emergency mode is active, but SMS notifications could "
                "not be started: " + str(exc),
            }
    return jsonify(
        {
            "success": True,
            "changed": changed,
            "message": "Emergency mode activated." if active else "Emergency mode deactivated.",
            "emergency": emergency,
            "smsNotification": sms_notification,
        }
    )


@bp.route("/api/queue/next-number")
@login_required_api
def api_next_number():
    return jsonify({"queueNumber": repository.generate_next_queue_number()})


@bp.route("/api/queue/register", methods=["POST"])
@login_required_api
def api_register():
    data = request.get_json() or {}
    name = (data.get("patientName") or "").strip()
    service = data.get("serviceType") or ""
    room = data.get("assignedRoom") or ""
    sms = bool(data.get("smsNotify"))
    patient_phone = (data.get("patientPhone") or "").strip()
    patient_priority = (data.get("patientPriority") or "Regular").strip()

    if not name:
        return jsonify({"success": False, "message": "Patient name is required."}), 400
    if not service or not room:
        return jsonify({"success": False, "message": "Service and room are required."}), 400
    if sms and not patient_phone:
        return jsonify({"success": False, "message": "Patient number is required when SMS notification is enabled."}), 400
    if sms:
        try:
            patient_phone = validate_phone_number(patient_phone)
        except SmsError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400

    patient = repository.register_patient(
        name,
        service,
        room,
        sms,
        patient_phone,
        patient_priority,
    )
    emergency_notification = None
    if patient.get("priority") == "Emergency":
        try:
            emergency, _ = repository.activate_emergency(
                session["user"].get("userId")
            )
            if emergency.get("emergencyId"):
                emergency_notification = repository.send_emergency_queue_notice(
                    emergency["emergencyId"]
                )
            else:
                emergency_notification = {
                    "status": "failed",
                    "sent": 0,
                    "failed": 0,
                    "skipped": 0,
                    "failures": [],
                    "message": "Emergency record was not available for notification.",
                }
        except Error as exc:
            emergency_notification = {
                "status": "failed",
                "sent": 0,
                "failed": 0,
                "skipped": 0,
                "failures": [],
                "message": "Emergency patient was added, but notifications could not "
                "be started: " + str(exc),
            }
    return jsonify(
        {
            "success": True,
            "patient": patient,
            "emergencyNotification": emergency_notification,
        }
    )


@bp.route("/api/queue/reminders", methods=["POST"])
@login_required_api
def api_process_reminders():
    sent = repository.dispatch_pending_reminders()
    return jsonify({"success": True, "reminders": sent})


@bp.route("/api/queue/reminders/simulate", methods=["POST"])
@login_required_api
def api_simulate_reminders():
    preview = repository.get_reminder_simulation()
    return jsonify({"success": True, "simulation": preview})


@bp.route("/api/queue/call-next", methods=["POST"])
@login_required_api
def api_call_next():
    patient, err = repository.call_next_patient()
    if err:
        return jsonify({"success": False, "message": err}), 400
    sms_notification = repository.send_call_notification(patient)
    repository.dispatch_pending_reminders()
    return jsonify(
        {
            "success": True,
            "patient": patient,
            "smsNotification": sms_notification,
        }
    )


@bp.route("/api/queue/<int:queue_id>/skip", methods=["POST"])
@login_required_api
def api_skip(queue_id):
    patient, err = repository.skip_patient(queue_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    repository.dispatch_pending_reminders()
    return jsonify({"success": True, "patient": patient})


@bp.route("/api/queue/<int:queue_id>/cancel", methods=["POST"])
@login_required_api
def api_cancel(queue_id):
    patient, err = repository.cancel_patient(queue_id)
    if err:
        return jsonify({"success": False, "message": err}), 400
    repository.dispatch_pending_reminders()
    return jsonify({"success": True, "patient": patient})


@bp.route("/api/queue/<int:queue_id>/move/<string:direction>", methods=["POST"])
@login_required_api
def api_move(queue_id, direction):
    if direction not in ("up", "down"):
        return jsonify({"success": False, "message": "Invalid queue direction."}), 400
    patient, err = repository.move_patient(queue_id, direction)
    if err:
        return jsonify({"success": False, "message": err}), 400
    repository.dispatch_pending_reminders()
    return jsonify({"success": True, "patient": patient})


@bp.route("/api/queue/<int:queue_id>/recall", methods=["POST"])
@login_required_api
def api_recall(queue_id):
    patient, err = repository.recall_patient(queue_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    repository.dispatch_pending_reminders()
    return jsonify({"success": True, "patient": patient})


@bp.route("/api/queue/complete", methods=["POST"])
@login_required_api
def api_complete():
    data = request.get_json() or {}
    queue_id = data.get("queueId")
    patient, err = repository.complete_patient(queue_id)
    if err:
        return jsonify({"success": False, "message": err}), 400
    repository.dispatch_pending_reminders()
    return jsonify({"success": True, "patient": patient})


# ----- Staff Analytics API -----


@bp.route("/api/analytics/staff")
@login_required_api
def api_staff_analytics():
    return jsonify(repository.get_staff_analytics())


# ----- Results Release API -----


@bp.route("/api/results")
@login_required_api
def api_results_list():
    filter_status = request.args.get("filter", "All")
    return jsonify(repository.get_results_list(filter_status))


@bp.route("/api/results/<int:queue_id>/ready", methods=["POST"])
@login_required_api
def api_mark_ready(queue_id):
    data = request.get_json() or {}
    send_sms = data.get("sendNotification", True)
    patient, msg = repository.mark_ready_for_release(queue_id, send_sms)
    if patient is None:
        return jsonify({"success": False, "message": msg}), 400
    return jsonify({"success": True, "patient": patient, "notificationMessage": msg})


@bp.route("/api/results/<int:queue_id>/released", methods=["POST"])
@login_required_api
def api_mark_released(queue_id):
    patient, err = repository.mark_result_released(queue_id)
    if err:
        return jsonify({"success": False, "message": err}), 400
    return jsonify({"success": True, "patient": patient})


@bp.route("/api/results/<int:queue_id>/notify", methods=["POST"])
@login_required_api
def api_notify_result(queue_id):
    patient, msg = repository.send_result_notification(queue_id)
    if patient is None:
        return jsonify({"success": False, "message": msg}), 400
    return jsonify({"success": True, "patient": patient, "notificationMessage": msg})
