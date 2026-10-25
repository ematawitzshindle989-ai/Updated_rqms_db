"""SIM800C GSM modem SMS transport."""

import re
import time

import serial
from serial import SerialException

from config import Config


PHONE_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")


class SmsError(Exception):
    """Raised when the SIM800C cannot send an SMS."""


def validate_phone_number(phone):
    normalized = re.sub(r"[\s()-]", "", phone or "")
    if normalized.startswith("09") and len(normalized) == 11:
        normalized = "+63" + normalized[1:]
    if not PHONE_PATTERN.fullmatch(normalized):
        raise SmsError("Please enter a valid mobile number.")
    return normalized


def _read_until(modem, expected, timeout=None, stage="modem response"):
    deadline = time.monotonic() + (
        Config.SIM800C_TIMEOUT if timeout is None else timeout
    )
    response = b""
    while time.monotonic() < deadline:
        response += modem.read_all()
        text = response.decode(errors="replace")
        if "ERROR" in text:
            raise SmsError("SIM800C returned an error: " + text.strip())
        if expected in text:
            return text
        time.sleep(0.05)
    raise SmsError(
        "Timed out waiting for "
        + expected
        + " during "
        + stage
        + " on "
        + Config.SIM800C_PORT
        + ". Check the configured AT-command port and baud rate, and confirm the "
        "modem is responding."
    )


def _send_command(modem, command):
    modem.write(command.encode("ascii") + b"\r")
    return _read_until(modem, "OK", stage="AT command " + command)


def _send_sim800c(phone, message, check_readiness=False):
    """Send one SMS through SIM800C text mode and wait for confirmation."""
    number = validate_phone_number(phone)
    try:
        with serial.Serial(
            Config.SIM800C_PORT,
            Config.SIM800C_BAUDRATE,
            timeout=0.2,
            write_timeout=Config.SIM800C_TIMEOUT,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        ) as modem:
            _send_command(modem, "AT")
            if check_readiness:
                sim_response = _send_command(modem, "AT+CPIN?")
                if "+CPIN: READY" not in sim_response:
                    raise SmsError(
                        "SIM card is not ready. Check SIM800C AT+CPIN? status."
                    )
                registration_response = _send_command(modem, "AT+CREG?")
                if not re.search(
                    r"\+CREG:\s*\d+,\s*[15](?:\D|$)", registration_response
                ):
                    raise SmsError(
                        "SIM800C is not registered on the GSM network. Check the SIM "
                        "card, antenna, and network coverage."
                    )
            _send_command(modem, "AT+CMGF=1")
            modem.write(('AT+CMGS="{}"\r'.format(number)).encode())
            _read_until(modem, ">", stage="SMS recipient prompt (AT+CMGS)")
            modem.write(message.encode("ascii", errors="replace") + b"\x1a")
            response = _read_until(
                modem, "OK", timeout=30, stage="SMS send confirmation (+CMGS)"
            )
            if "+CMGS:" not in response:
                raise SmsError("SIM800C did not confirm SMS delivery.")
    except (SerialException, OSError) as exc:
        raise SmsError(
            "Could not open or communicate with "
            + Config.SIM800C_PORT
            + ". Make sure the SIM800C is connected and close Arduino IDE Serial "
            "Monitor, PuTTY, or any other program using the port. Details: "
            + str(exc)
        ) from exc


def send_sms(phone, message):
    """Send through the configured transport and return its delivery label."""
    number = validate_phone_number(phone)
    if Config.SMS_MODE == "simulation":
        return "Simulation Sent"
    if Config.SMS_MODE == "sim800c":
        _send_sim800c(number, message, check_readiness=True)
        return "Sent"
    raise SmsError("Unsupported SMS_MODE. Use 'simulation' or 'sim800c'.")
