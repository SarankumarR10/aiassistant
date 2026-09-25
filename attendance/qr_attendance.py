"""Signed, short-lived attendance tokens for in-person classroom check-in."""
from datetime import date
import hashlib
import hmac
import time

from database.database import get_or_create_app_secret, mark_student_attendance_from_qr


class QRAttendanceSystem:
    TOKEN_PREFIX = "EDUPILOT"
    TOKEN_TTL_SECONDS = 300

    def __init__(self):
        self.secret_key = get_or_create_app_secret("attendance_qr_hmac_key")

    def generate_token(self, subject_id: int, date_str: str, faculty_id: int = 0, section: str = "C") -> str:
        if date_str != date.today().isoformat():
            raise ValueError("QR attendance can only be opened for today's class.")
        expiry = int(time.time()) + self.TOKEN_TTL_SECONDS
        if not section or ":" in section:
            raise ValueError("Choose a valid class section before opening QR check-in.")
        payload = f"{subject_id}:{date_str}:{expiry}:{faculty_id}:{section}"
        signature = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return f"{self.TOKEN_PREFIX}:{payload}:{signature}"

    def validate_token(self, qr_text: str) -> dict:
        try:
            prefix, subject_id, date_str, expires, faculty_id, section, signature = qr_text.strip().split(":")
            payload = f"{subject_id}:{date_str}:{expires}:{faculty_id}:{section}"
            expected = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
            expires_at = int(expires)
            valid = (
                prefix == self.TOKEN_PREFIX
                and int(subject_id) > 0 and int(faculty_id) > 0 and bool(section)
                and date_str == date.today().isoformat()
                and int(time.time()) < expires_at <= int(time.time()) + self.TOKEN_TTL_SECONDS + 10
                and hmac.compare_digest(signature, expected)
            )
            if not valid:
                return {"valid": False, "error": "This attendance code is invalid or has expired."}
            return {"valid": True, "subject_id": int(subject_id), "date": date_str,
                    "faculty_id": int(faculty_id), "section": section, "expires_at": expires_at}
        except (ValueError, TypeError):
            return {"valid": False, "error": "This attendance code is invalid or has expired."}

    def record_attendance(self, user_id: int, qr_text: str) -> None:
        result = self.validate_token(qr_text)
        if not result["valid"]:
            raise ValueError(result["error"])
        mark_student_attendance_from_qr(
            user_id, result["subject_id"], result["date"], result["faculty_id"], result["section"]
        )
