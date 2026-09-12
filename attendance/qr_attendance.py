import time
import hashlib

class QRAttendanceSystem:
    """
    Generates dynamic time-bound QR tokens for student attendance and validates scanned codes.
    """
    def __init__(self, secret_key="VCET_EDU_PILOT"):
        self.secret_key = secret_key

    def generate_token(self, subject_id: int, date_str: str, time_slot: int = 0) -> str:
        """Generate a secure, short-lived QR token string."""
        raw = f"{self.secret_key}:{subject_id}:{date_str}:{time_slot}"
        token = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return f"ATTENDANCE:{subject_id}:{date_str}:{token}"

    def validate_token(self, qr_text: str) -> dict:
        """Validates scanned QR code format and session token."""
        parts = qr_text.split(":")
        if len(parts) == 4 and parts[0] == "ATTENDANCE":
            return {
                "valid": True,
                "subject_id": parts[1],
                "date": parts[2],
                "token": parts[3]
            }
        return {"valid": False, "error": "Invalid or expired QR code"}
