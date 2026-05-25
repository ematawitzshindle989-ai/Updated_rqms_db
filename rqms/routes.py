"""Web pages and REST API routes."""

from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from rqms import repository
from rqms.db import test_connection

bp = Blueprint("rqms", __name__)


def login_required_page(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("rqms.login_page"))
        return f(*args, **kwargs)

    return wrapped


def login_required_api(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "message": "Not authenticated."}), 401
        return f(*args, **kwargs)

    return wrapped


def admin_required_api(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "message": "Not authenticated."}), 401
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


# ----- Auth API -----


@bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role") or ""

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
    return jsonify({"authenticated": True, "user": session["user"]})


# ----- Database API -----


@bp.route("/api/health")
def api_health():
    ok, message = test_connection()
    return jsonify({"connected": ok, "message": message})


@bp.route("/api/admin/config")
@admin_required_api
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


# ----- Queue API -----


@bp.route("/api/queue/dashboard")
@login_required_api
def api_dashboard():
    return jsonify(
        {
            "activeQueue": repository.get_active_queue(),
            "stats": repository.get_queue_stats(),
            "current": repository.get_current_serving(),
        }
    )


@bp.route("/api/queue/display")
def api_display():
    return jsonify(
        {
            "current": repository.get_current_serving(),
            "upcoming": [
                p
                for p in repository.get_active_queue()
                if p["status"] == repository.QUEUE_STATUS["WAITING"]
            ][:6],
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

    patient = repository.register_patient(
        name,
        service,
        room,
        sms,
        patient_phone,
        patient_priority,
    )
    return jsonify({"success": True, "patient": patient})


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
    return jsonify({"success": True, "patient": patient})


@bp.route("/api/queue/<int:queue_id>/skip", methods=["POST"])
@login_required_api
def api_skip(queue_id):
    patient, err = repository.skip_patient(queue_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "patient": patient})


@bp.route("/api/queue/<int:queue_id>/recall", methods=["POST"])
@login_required_api
def api_recall(queue_id):
    patient, err = repository.recall_patient(queue_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "patient": patient})


@bp.route("/api/queue/complete", methods=["POST"])
@login_required_api
def api_complete():
    data = request.get_json() or {}
    queue_id = data.get("queueId")
    patient, err = repository.complete_patient(queue_id)
    if err:
        return jsonify({"success": False, "message": err}), 400
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
