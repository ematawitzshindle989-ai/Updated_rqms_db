import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from serial import SerialException
from werkzeug.security import check_password_hash

from rqms import repository
from rqms import db
from rqms import sms
from rqms import routes
from rqms.routes import bp


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.executed = []
        self.lastrowid = 17
        self.rowcount = 1

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self.row

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False

    def cursor(self, **kwargs):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def close(self):
        pass


class SchemaUpgradeCursor:
    def __init__(self, existing_columns=()):
        self.existing_columns = set(existing_columns)
        self.current_column = None
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if query.startswith("SHOW COLUMNS"):
            self.current_column = params[0]

    def fetchone(self):
        if self.current_column in self.existing_columns:
            return {"Field": self.current_column}
        return None

    def close(self):
        self.closed = True


class AccountHandlerRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(
            __name__,
            template_folder=str(Path(__file__).resolve().parents[1] / "templates"),
            static_folder=str(Path(__file__).resolve().parents[1] / "static"),
        )
        cls.app.config.update(SECRET_KEY="account-handler-test")
        cls.app.register_blueprint(bp)
        cls.app.testing = True

    def setUp(self):
        self.client = self.app.test_client()
        self.active_account = patch.object(repository, "is_account_active", return_value=True)
        self.active_account.start()
        self.addCleanup(self.active_account.stop)

    def authenticate(self, role):
        with self.client.session_transaction() as session:
            session["user"] = {
                "userId": 2,
                "username": "tester",
                "fullName": "Test User",
                "role": role,
            }

    def test_staff_cannot_view_account_handler_or_staff_api(self):
        self.authenticate("Staff")
        self.assertEqual(self.client.get("/account-handler").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/staff").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/admin/staff",
                json={
                    "fullName": "Unauthorized",
                    "username": "unauthorized",
                    "password": "password123",
                },
            ).status_code,
            403,
        )

    def test_dashboard_shows_account_handler_link_only_to_admin(self):
        self.authenticate("Admin")
        admin_dashboard = self.client.get("/dashboard")
        self.assertEqual(admin_dashboard.status_code, 200)
        self.assertIn(b"Account Handler", admin_dashboard.data)

        self.authenticate("Staff")
        staff_dashboard = self.client.get("/dashboard")
        self.assertEqual(staff_dashboard.status_code, 200)
        self.assertNotIn(b"Account Handler", staff_dashboard.data)

    def test_admin_can_view_account_handler_and_create_staff_only(self):
        self.authenticate("Admin")
        with patch.object(repository, "get_staff_accounts", return_value=[]):
            self.assertEqual(self.client.get("/account-handler").status_code, 200)
            self.assertEqual(self.client.get("/api/admin/staff").json, {"staff": []})

        with patch.object(repository, "create_staff_account", return_value=17) as create:
            response = self.client.post(
                "/api/admin/staff",
                json={
                    "fullName": "Radiology Staff",
                    "username": "rad.staff",
                    "password": "securepass123",
                    "role": "Admin",
                },
            )
        self.assertEqual(response.status_code, 201)
        create.assert_called_once_with("rad.staff", "securepass123", "Radiology Staff")

    def test_create_requires_strong_password_and_valid_staff_username(self):
        self.authenticate("Admin")
        response = self.client.post(
            "/api/admin/staff",
            json={"fullName": "Radiology Staff", "username": "rad", "password": "1234"},
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_can_edit_reset_toggle_and_delete_staff_accounts(self):
        self.authenticate("Admin")
        with (
            patch.object(repository, "update_staff_account", return_value=True) as update,
            patch.object(repository, "reset_staff_password", return_value=True) as reset,
            patch.object(repository, "set_staff_account_active", return_value=True) as set_active,
            patch.object(repository, "delete_staff_account", return_value=True) as delete,
        ):
            edit_response = self.client.put(
                "/api/admin/staff/7",
                json={"fullName": "Updated Name", "username": "updated.staff"},
            )
            password_response = self.client.post(
                "/api/admin/staff/7/password",
                json={"password": "newsecurepass"},
            )
            status_response = self.client.patch(
                "/api/admin/staff/7/status",
                json={"isActive": False},
            )
            delete_response = self.client.delete("/api/admin/staff/7")

        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(password_response.status_code, 200)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)
        update.assert_called_once_with(7, "updated.staff", "Updated Name")
        reset.assert_called_once_with(7, "newsecurepass")
        set_active.assert_called_once_with(7, False)
        delete.assert_called_once_with(7)

    def test_inactive_user_session_is_rejected(self):
        self.authenticate("Staff")
        self.active_account.stop()
        with patch.object(repository, "is_account_active", return_value=False):
            response = self.client.get("/api/admin/staff")
        self.assertEqual(response.status_code, 401)

    def test_call_next_keeps_queue_successful_when_patient_sms_fails(self):
        self.authenticate("Staff")
        patient = {
            "queueId": 22,
            "queueNumber": "R133",
            "assignedRoom": "Ultrasound Room 1",
            "smsEnabled": True,
        }
        with (
            patch.object(repository, "call_next_patient", return_value=(patient, None)),
            patch.object(
                repository,
                "send_call_notification",
                return_value={"status": "Failed", "message": "Modem unavailable."},
            ) as notify,
            patch.object(repository, "dispatch_pending_reminders"),
        ):
            response = self.client.post("/api/queue/call-next")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(
            response.json["smsNotification"]["message"], "Modem unavailable."
        )
        notify.assert_called_once_with(patient)

    def test_emergency_mode_activation_sends_notice_only_when_new(self):
        self.authenticate("Staff")
        incident = {"emergencyId": 35, "active": True}
        with (
            patch.object(repository, "activate_emergency", return_value=(incident, True)),
            patch.object(repository, "send_emergency_queue_notice", return_value={"sent": 2}) as send,
        ):
            response = self.client.post("/api/queue/emergency", json={"active": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["smsNotification"], {"sent": 2})
        send.assert_called_once_with(35)

    def test_reactivating_existing_emergency_does_not_repeat_notice(self):
        self.authenticate("Staff")
        incident = {"emergencyId": 35, "active": True}
        with (
            patch.object(repository, "activate_emergency", return_value=(incident, False)),
            patch.object(repository, "send_emergency_queue_notice") as send,
        ):
            response = self.client.post("/api/queue/emergency", json={"active": True})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json["smsNotification"])
        send.assert_not_called()

    def test_registering_emergency_patient_activates_incident_after_insertion(self):
        self.authenticate("Staff")
        patient = {
            "queueId": 23,
            "queueNumber": "R134",
            "priority": "Emergency",
        }
        incident = {"emergencyId": 36, "active": True}
        with (
            patch.object(repository, "register_patient", return_value=patient) as register,
            patch.object(repository, "activate_emergency", return_value=(incident, True)) as activate,
            patch.object(repository, "send_emergency_queue_notice", return_value={"sent": 3}) as send,
        ):
            response = self.client.post(
                "/api/queue/register",
                json={
                    "patientName": "Emergency Patient",
                    "serviceType": "X-Ray",
                    "assignedRoom": "X-Ray Room 1",
                    "patientPriority": "Emergency",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["emergencyNotification"], {"sent": 3})
        register.assert_called_once()
        activate.assert_called_once_with(2)
        send.assert_called_once_with(36)

    def test_emergency_sms_failure_does_not_fail_patient_registration(self):
        self.authenticate("Staff")
        patient = {
            "queueId": 23,
            "queueNumber": "R134",
            "priority": "Emergency",
        }
        with (
            patch.object(repository, "register_patient", return_value=patient),
            patch.object(
                repository,
                "activate_emergency",
                return_value=({"emergencyId": 36}, True),
            ),
            patch.object(
                repository,
                "send_emergency_queue_notice",
                return_value={
                    "status": "failed",
                    "sent": 0,
                    "failed": 1,
                    "skipped": 0,
                    "failures": [{"queueNumber": "R133", "message": "Network error"}],
                    "message": "Some emergency SMS notifications failed.",
                },
            ),
        ):
            response = self.client.post(
                "/api/queue/register",
                json={
                    "patientName": "Emergency Patient",
                    "serviceType": "X-Ray",
                    "assignedRoom": "X-Ray Room 1",
                    "patientPriority": "Emergency",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["patient"], patient)
        self.assertEqual(response.json["emergencyNotification"]["failed"], 1)


class AccountPasswordTests(unittest.TestCase):
    def test_staff_account_creation_hashes_password_and_sets_staff_role(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        with patch.object(repository, "get_connection", return_value=connection):
            user_id = repository.create_staff_account("nurse1", "securepass123", "Nurse One")

        query, values = cursor.executed[0]
        self.assertIn("'Staff'", query)
        self.assertEqual(user_id, 17)
        self.assertEqual(values[0], "nurse1")
        self.assertTrue(check_password_hash(values[1], "securepass123"))
        self.assertEqual(values[2], "Nurse One")

    def test_delete_targets_staff_and_detaches_emergency_audit_references(self):
        cursor = FakeCursor(row=(1,))
        connection = FakeConnection(cursor)
        with patch.object(repository, "get_connection", return_value=connection):
            deleted = repository.delete_staff_account(17)

        self.assertTrue(deleted)
        self.assertIn("SET activated_by = CASE", cursor.executed[1][0])
        self.assertIn("DELETE FROM users WHERE user_id = %s AND role = 'Staff'", cursor.executed[2][0])
        self.assertTrue(connection.committed)

    def test_delete_does_not_touch_admin_audit_references(self):
        cursor = FakeCursor(row=None)
        connection = FakeConnection(cursor)
        with patch.object(repository, "get_connection", return_value=connection):
            deleted = repository.delete_staff_account(1)

        self.assertFalse(deleted)
        self.assertEqual(len(cursor.executed), 1)
        self.assertFalse(connection.committed)

    def test_legacy_password_is_upgraded_after_successful_login(self):
        cursor = FakeCursor(
            {
                "user_id": 2,
                "username": "staff",
                "password": "1234",
                "full_name": "Staff User",
                "role": "Staff",
                "is_active": 1,
            }
        )
        connection = FakeConnection(cursor)
        with patch.object(repository, "get_connection", return_value=connection):
            user = repository.try_login("staff", "1234", "Staff")

        self.assertEqual(user["role"], "Staff")
        self.assertEqual(cursor.executed[0][1], ("staff", "Staff"))
        self.assertIn("UPDATE users SET password", cursor.executed[1][0])
        self.assertTrue(check_password_hash(cursor.executed[1][1][0], "1234"))

    def test_staff_account_created_with_hash_can_log_in(self):
        password = "securepass123"
        cursor = FakeCursor(
            {
                "user_id": 17,
                "username": "nurse1",
                "password": repository.generate_password_hash(password),
                "full_name": "Nurse One",
                "role": "Staff",
                "is_active": 1,
            }
        )
        connection = FakeConnection(cursor)
        with patch.object(repository, "get_connection", return_value=connection):
            user = repository.try_login("nurse1", password, "Staff")

        self.assertEqual(user["userId"], 17)
        self.assertEqual(user["role"], "Staff")
        self.assertEqual(len(cursor.executed), 1)

    def test_inactive_staff_cannot_log_in(self):
        cursor = FakeCursor(
            {
                "user_id": 2,
                "username": "staff",
                "password": "1234",
                "full_name": "Staff User",
                "role": "Staff",
                "is_active": 0,
            }
        )
        connection = FakeConnection(cursor)
        with patch.object(repository, "get_connection", return_value=connection):
            user = repository.try_login("staff", "1234", "Staff")
        self.assertIsNone(user)
        self.assertEqual(len(cursor.executed), 1)


class FakeModem:
    def __init__(self, responses):
        self.responses = list(responses)
        self.writes = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.closed = True

    def write(self, data):
        self.writes.append(data)

    def read_all(self):
        return self.responses.pop(0) if self.responses else b""


class Sim800cSmsTests(unittest.TestCase):
    def test_configured_hardware_mode_uses_sim800c_for_workflow_sms(self):
        with (
            patch.object(sms.Config, "SMS_MODE", "sim800c"),
            patch.object(sms, "_send_sim800c") as send,
        ):
            status = sms.send_sms("09171234567", "R133, please proceed.")

        self.assertEqual(status, "Sent")
        send.assert_called_once_with(
            "+639171234567",
            "R133, please proceed.",
            check_readiness=True,
        )

    def test_hardware_sms_sends_message_and_ctrl_z(self):
        modem = FakeModem(
            [
                b"AT\r\nOK\r\n",
                b"AT+CPIN?\r\n+CPIN: READY\r\nOK\r\n",
                b"AT+CREG?\r\n+CREG: 0,1\r\nOK\r\n",
                b"AT+CMGF=1\r\nOK\r\n",
                b"\r\n>",
                b"\r\n+CMGS: 42\r\nOK\r\n",
            ]
        )
        with (
            patch.object(sms.serial, "Serial", return_value=modem) as serial_open,
            patch.object(sms.Config, "SMS_MODE", "simulation"),
        ):
            sms._send_sim800c(
                "09171234567", "R133, please proceed.", check_readiness=True
            )

        serial_open.assert_called_once()
        self.assertEqual(serial_open.call_args.args[:2], ("COM3", 9600))
        self.assertFalse(serial_open.call_args.kwargs["xonxoff"])
        self.assertFalse(serial_open.call_args.kwargs["rtscts"])
        self.assertEqual(modem.writes[-1], b"R133, please proceed.\x1a")
        self.assertEqual(
            modem.writes,
            [
                b"AT\r",
                b"AT+CPIN?\r",
                b"AT+CREG?\r",
                b"AT+CMGF=1\r",
                b'AT+CMGS="+639171234567"\r',
                b"R133, please proceed.\x1a",
            ],
        )
        self.assertTrue(modem.closed)

    def test_sms_fails_clearly_when_sim_is_not_ready(self):
        modem = FakeModem([b"OK\r\n", b"+CPIN: SIM PIN\r\nOK\r\n"])
        with patch.object(sms.serial, "Serial", return_value=modem):
            with self.assertRaisesRegex(sms.SmsError, "SIM card is not ready"):
                sms._send_sim800c(
                    "+639171234567", "Test body", check_readiness=True
                )
        self.assertTrue(modem.closed)
        self.assertEqual(modem.writes, [b"AT\r", b"AT+CPIN?\r"])

    def test_sms_fails_clearly_when_modem_is_not_registered(self):
        modem = FakeModem(
            [b"OK\r\n", b"+CPIN: READY\r\nOK\r\n", b"+CREG: 0,2\r\nOK\r\n"]
        )
        with patch.object(sms.serial, "Serial", return_value=modem):
            with self.assertRaisesRegex(sms.SmsError, "not registered"):
                sms._send_sim800c(
                    "+639171234567", "Test body", check_readiness=True
                )
        self.assertTrue(modem.closed)

    def test_sms_reports_at_command_errors(self):
        modem = FakeModem([b"\r\nERROR\r\n"])
        with patch.object(sms.serial, "Serial", return_value=modem):
            with self.assertRaisesRegex(sms.SmsError, "SIM800C returned an error"):
                sms._send_sim800c(
                    "+639171234567", "Test body", check_readiness=True
                )
        self.assertTrue(modem.closed)

    def test_sms_reports_a_busy_or_unavailable_com_port(self):
        with patch.object(
            sms.serial, "Serial", side_effect=SerialException("Access is denied")
        ):
            with self.assertRaisesRegex(sms.SmsError, "close Arduino IDE Serial Monitor"):
                sms._send_sim800c(
                    "+639171234567", "Test body", check_readiness=True
                )

    def test_sms_reports_a_missing_sms_confirmation(self):
        modem = FakeModem(
            [
                b"OK\r\n",
                b"+CPIN: READY\r\nOK\r\n",
                b"+CREG: 0,1\r\nOK\r\n",
                b"OK\r\n",
                b">",
                b"OK\r\n",
            ]
        )
        with patch.object(sms.serial, "Serial", return_value=modem):
            with self.assertRaisesRegex(sms.SmsError, "did not confirm SMS delivery"):
                sms._send_sim800c(
                    "+639171234567", "Test body", check_readiness=True
                )
        self.assertTrue(modem.closed)

    def test_sms_prompt_timeout_is_bounded_and_actionable(self):
        modem = FakeModem(
            [
                b"OK\r\n",
                b"+CPIN: READY\r\nOK\r\n",
                b"+CREG: 0,1\r\nOK\r\n",
                b"OK\r\n",
            ]
        )
        with (
            patch.object(sms.serial, "Serial", return_value=modem),
            patch.object(sms.Config, "SIM800C_TIMEOUT", 0.01),
            patch.object(sms.time, "sleep"),
        ):
            with self.assertRaisesRegex(
                sms.SmsError, "Timed out waiting for > during SMS recipient prompt.*COM3"
            ):
                sms._send_sim800c(
                    "+639171234567", "Test body", check_readiness=True
                )
        self.assertTrue(modem.closed)


class QueueCallSmsIntegrationTests(unittest.TestCase):
    def test_emergency_priority_sorts_ahead_of_other_queue_priorities(self):
        patients = [
            {"priority": "Regular", "registeredAt": "2026-01-01"},
            {"priority": "Priority", "registeredAt": "2026-01-02"},
            {"priority": "Emergency", "registeredAt": "2026-01-03"},
        ]
        self.assertEqual(
            [patient["priority"] for patient in sorted(patients, key=repository._queue_sort_key)],
            ["Emergency", "Priority", "Regular"],
        )

    def test_call_sms_uses_queue_number_and_assigned_room(self):
        patient = {
            "queueId": 22,
            "queueNumber": "R133",
            "assignedRoom": "Ultrasound Room 1",
            "patientPhone": "+639171234567",
            "smsEnabled": True,
        }
        with (
            patch.object(repository, "send_sms", return_value="Sent") as send,
            patch.object(repository, "record_sms_log") as log,
        ):
            result = repository.send_call_notification(patient)

        expected_message = "R133, please proceed to Ultrasound Room 1."
        send.assert_called_once_with("+639171234567", expected_message)
        log.assert_called_once_with(patient, "Patient Called", expected_message, "Sent")
        self.assertEqual(result, {"status": "Sent", "message": expected_message})

    def test_call_sms_skips_patients_who_did_not_opt_in(self):
        patient = {"smsEnabled": False}
        with (
            patch.object(repository, "send_sms") as send,
            patch.object(repository, "record_sms_log") as log,
        ):
            result = repository.send_call_notification(patient)

        send.assert_not_called()
        log.assert_not_called()
        self.assertEqual(
            result,
            {"status": "Skipped", "message": "SMS notification is not enabled."},
        )

    def test_call_sms_failure_is_logged_and_does_not_raise(self):
        patient = {
            "queueId": 22,
            "queueNumber": "R133",
            "assignedRoom": "X-Ray Room 2",
            "patientPhone": "+639171234567",
            "smsEnabled": True,
        }
        with (
            patch.object(
                repository, "send_sms", side_effect=sms.SmsError("Network unavailable.")
            ),
            patch.object(repository, "record_sms_log") as log,
        ):
            result = repository.send_call_notification(patient)

        log.assert_called_once_with(
            patient,
            "Patient Called",
            "R133, please proceed to X-Ray Room 2.",
            "Failed",
        )
        self.assertEqual(result, {"status": "Failed", "message": "Network unavailable."})

    def test_emergency_notice_targets_only_waiting_opted_in_regular_patients(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        waiting_patients = [
            {
                "queueId": 1, "queueNumber": "R133", "patientName": "One",
                "patientPhone": "09171234567", "smsEnabled": True,
                "priority": "Regular", "status": "Waiting",
            },
            {
                "queueId": 2, "queueNumber": "R134", "patientName": "Two",
                "patientPhone": "+639181234567", "smsEnabled": True,
                "priority": "Regular", "status": "Waiting",
            },
            {
                "queueId": 3, "queueNumber": "R135", "patientName": "Three",
                "patientPhone": "invalid", "smsEnabled": True,
                "priority": "Regular", "status": "Waiting",
            },
            {
                "queueId": 4, "queueNumber": "R136", "patientName": "Four",
                "patientPhone": "+639191234567", "smsEnabled": False,
                "priority": "Regular", "status": "Waiting",
            },
            {
                "queueId": 5, "queueNumber": "R137", "patientName": "Five",
                "patientPhone": "+639201234567", "smsEnabled": True,
                "priority": "Priority", "status": "Waiting",
            },
            {
                "queueId": 6, "queueNumber": "R138", "patientName": "Six",
                "patientPhone": "+639211234567", "smsEnabled": True,
                "priority": "Regular", "status": "Called",
            },
        ]
        with (
            patch.object(repository, "get_connection", return_value=connection),
            patch.object(repository, "get_active_queue", return_value=waiting_patients),
            patch.object(repository, "send_sms", return_value="Sent") as send,
            patch.object(repository, "record_sms_log") as log,
        ):
            result = repository.send_emergency_queue_notice(8)

        self.assertEqual(result["status"], "sent")
        self.assertEqual((result["sent"], result["failed"], result["skipped"]), (2, 0, 2))
        self.assertEqual(
            [call.args[0] for call in send.call_args_list],
            ["+639171234567", "+639181234567"],
        )
        send.assert_any_call(
            "+639171234567",
            repository.EMERGENCY_QUEUE_MESSAGE,
        )
        self.assertEqual(log.call_count, 2)
        self.assertIn("WHERE emergency_id = %s AND sms_notification_started_at IS NULL",
                      cursor.executed[0][0])
        self.assertTrue(connection.committed)

    def test_emergency_notice_is_not_repeated_for_an_incident(self):
        cursor = FakeCursor()
        cursor.rowcount = 0
        with (
            patch.object(
                repository, "get_connection", return_value=FakeConnection(cursor)
            ),
            patch.object(repository, "get_active_queue") as active_queue,
            patch.object(repository, "send_sms") as send,
        ):
            result = repository.send_emergency_queue_notice(8)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["sent"], 0)
        active_queue.assert_not_called()
        send.assert_not_called()

    def test_emergency_sms_failure_is_reported_and_logged_without_raising(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        patient = {
            "queueId": 1, "queueNumber": "R133", "patientName": "One",
            "patientPhone": "+639171234567", "smsEnabled": True,
            "priority": "Regular", "status": "Waiting",
        }
        with (
            patch.object(repository, "get_connection", return_value=connection),
            patch.object(repository, "get_active_queue", return_value=[patient]),
            patch.object(
                repository, "send_sms", side_effect=sms.SmsError("Network unavailable.")
            ),
            patch.object(repository, "record_sms_log") as log,
        ):
            result = repository.send_emergency_queue_notice(8)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failures"][0]["queueNumber"], "R133")
        log.assert_called_once_with(
            patient,
            "Emergency Queue Notice",
            repository.EMERGENCY_QUEUE_MESSAGE,
            "Failed",
        )

    def test_five_away_reminder_counts_only_waiting_patients_in_queue_order(self):
        called = {
            "queueId": 1, "queueNumber": "R100", "status": "Called",
            "priority": "Regular", "smsEnabled": True,
            "patientPhone": "+639171234567", "reminderStatus": "Not Sent",
        }
        waiting = [
            {
                "queueId": index + 2,
                "queueNumber": "R{}".format(101 + index),
                "status": "Waiting",
                "priority": "Regular",
                "smsEnabled": True,
                "patientPhone": "+63917123456{}".format(index),
                "reminderStatus": "Not Sent",
                "reminderSent": False,
                "patientName": "Patient {}".format(index),
            }
            for index in range(7)
        ]
        with (
            patch.object(
                repository, "get_active_queue", return_value=[called] + waiting
            ),
            patch.object(repository, "_claim_queue_reminder", return_value=True) as claim,
            patch.object(repository, "send_sms", return_value="Sent") as send,
            patch.object(repository, "update_patient"),
            patch.object(repository, "record_sms_log") as log,
        ):
            results = repository.dispatch_pending_reminders()

        self.assertEqual([item["queueNumber"] for item in results], ["R106"])
        self.assertEqual(claim.call_args.args, (waiting[5]["queueId"],))
        send.assert_called_once_with(
            waiting[5]["patientPhone"],
            "ST. PAUL HOSPITAL - RADIOLOGY\n\n"
            "R106, you are 5 patients away from your turn. Please be ready and stay "
            "near the designated area.",
        )
        log.assert_called_once()
        self.assertTrue(waiting[5]["reminderSent"])

    def test_five_away_reminder_does_not_send_when_only_five_waiting(self):
        waiting = [
            {
                "queueId": index + 1,
                "queueNumber": "R{}".format(101 + index),
                "status": "Waiting",
                "priority": "Regular",
                "smsEnabled": True,
                "patientPhone": "+639171234567",
                "reminderStatus": "Not Sent",
                "reminderSent": False,
            }
            for index in range(5)
        ]
        with (
            patch.object(repository, "get_active_queue", return_value=waiting),
            patch.object(repository, "_claim_queue_reminder") as claim,
            patch.object(repository, "send_sms") as send,
        ):
            results = repository.dispatch_pending_reminders()

        self.assertEqual(results, [])
        claim.assert_not_called()
        send.assert_not_called()

    def test_five_away_reminder_skips_invalid_recipient_number(self):
        waiting = [
            {
                "queueId": index + 1,
                "queueNumber": "R{}".format(101 + index),
                "status": "Waiting",
                "priority": "Regular",
                "smsEnabled": index == 5,
                "patientPhone": "invalid" if index == 5 else "",
                "reminderStatus": "Not Sent",
                "reminderSent": False,
            }
            for index in range(6)
        ]
        with (
            patch.object(repository, "get_active_queue", return_value=waiting),
            patch.object(repository, "_claim_queue_reminder") as claim,
            patch.object(repository, "send_sms") as send,
        ):
            results = repository.dispatch_pending_reminders()

        self.assertEqual(results, [])
        claim.assert_not_called()
        send.assert_not_called()

    def test_atomic_reminder_claim_blocks_a_previously_claimed_attempt(self):
        cursor = FakeCursor()
        cursor.rowcount = 0
        connection = FakeConnection(cursor)
        with patch.object(repository, "get_connection", return_value=connection):
            claimed = repository._claim_queue_reminder(14)

        self.assertFalse(claimed)
        self.assertFalse(connection.committed)
        self.assertIn("reminder_status = 'Sending'", cursor.executed[0][0])
        self.assertIn("reminder_status, 'Not Sent')", cursor.executed[0][0])

    def test_five_away_reminder_is_not_retried_when_failed(self):
        waiting = [
            {
                "queueId": index + 1,
                "queueNumber": "R{}".format(101 + index),
                "status": "Waiting",
                "priority": "Regular",
                "smsEnabled": True,
                "patientPhone": "+639171234567",
                "reminderStatus": "Not Sent",
                "reminderSent": False,
                "patientName": "Patient {}".format(index),
            }
            for index in range(6)
        ]
        with (
            patch.object(repository, "get_active_queue", return_value=waiting),
            patch.object(repository, "_claim_queue_reminder", return_value=True),
            patch.object(
                repository, "send_sms", side_effect=sms.SmsError("Network unavailable.")
            ) as send,
            patch.object(repository, "update_patient"),
            patch.object(repository, "record_sms_log") as log,
        ):
            first_result = repository.dispatch_pending_reminders()
            second_result = repository.dispatch_pending_reminders()

        self.assertEqual(len(first_result), 1)
        self.assertTrue(first_result[0]["failed"])
        self.assertIn("Network unavailable.", first_result[0]["message"])
        self.assertEqual(second_result, [])
        send.assert_called_once()
        log.assert_called_once_with(
            waiting[5],
            "Queue Reminder",
            "ST. PAUL HOSPITAL - RADIOLOGY\n\n"
            "R106, you are 5 patients away from your turn. Please be ready and stay "
            "near the designated area.",
            "Failed",
        )

    def test_five_away_reminder_is_sent_after_queue_position_reaches_five_ahead(self):
        patient = {
            "queueId": 6,
            "queueNumber": "R106",
            "status": "Waiting",
            "priority": "Regular",
            "smsEnabled": True,
            "patientPhone": "+639171234567",
            "reminderStatus": "Not Sent",
            "reminderSent": False,
            "patientName": "Patient 6",
        }
        waiting_list_before_change = [
            {
                "queueId": index + 1,
                "queueNumber": "R{}".format(100 + index),
                "status": "Waiting",
                "priority": "Regular",
                "smsEnabled": False,
                "patientPhone": "",
                "reminderStatus": "Not Sent",
                "reminderSent": False,
            }
            for index in range(6)
        ] + [patient]
        waiting_list_after_change = waiting_list_before_change[1:]
        with (
            patch.object(
                repository,
                "get_active_queue",
                side_effect=[waiting_list_before_change, waiting_list_after_change],
            ),
            patch.object(repository, "_claim_queue_reminder", return_value=True),
            patch.object(repository, "send_sms", return_value="Sent") as send,
            patch.object(repository, "update_patient"),
            patch.object(repository, "record_sms_log"),
        ):
            before_change = repository.dispatch_pending_reminders()
            after_change = repository.dispatch_pending_reminders()

        self.assertEqual(before_change, [])
        self.assertEqual([item["queueNumber"] for item in after_change], ["R106"])
        send.assert_called_once()


class AccountSchemaUpgradeTests(unittest.TestCase):
    def test_startup_upgrade_adds_missing_account_status_column(self):
        cursor = SchemaUpgradeCursor()
        connection = FakeConnection(cursor)
        with patch.object(db, "get_connection", return_value=connection):
            db.ensure_result_columns()

        queries = [query for query, _ in cursor.executed]
        self.assertIn(
            "ALTER TABLE users MODIFY COLUMN password VARCHAR(255) NOT NULL",
            queries,
        )
        self.assertTrue(
            any("ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1" in query for query in queries)
        )
        self.assertTrue(
            any(
                "ADD COLUMN sms_notification_started_at DATETIME NULL" in query
                for query in queries
            )
        )
        self.assertTrue(connection.committed)
        self.assertTrue(cursor.closed)

    def test_startup_upgrade_does_not_add_existing_account_or_sms_columns_twice(self):
        cursor = SchemaUpgradeCursor(
            existing_columns={"is_active", "sms_notification_started_at"}
        )
        connection = FakeConnection(cursor)
        with patch.object(db, "get_connection", return_value=connection):
            db.ensure_result_columns()

        self.assertFalse(
            any(
                "ADD COLUMN is_active" in query
                for query, _ in cursor.executed
            )
        )
        self.assertFalse(
            any(
                "ADD COLUMN sms_notification_started_at" in query
                for query, _ in cursor.executed
            )
        )


if __name__ == "__main__":
    unittest.main()
