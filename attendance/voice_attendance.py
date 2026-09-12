"""
Voice-based Backup Attendance.
Allows students or faculty to mark attendance by speaking roll numbers.
"""
import re

def parse_voice_attendance_phrase(spoken_text: str) -> list:
    """
    Parses spoken roll numbers or phrases like 'Roll 1 present, Roll 2 present, Roll 3 absent'.
    Returns list of parsed records: [{'roll_number': '23CSE001', 'status': 'Present'}, ...]
    """
    results = []
    text = spoken_text.lower()

    # Pattern for roll numbers (e.g., 'roll 1 present', 'roll number 2 absent', '23cse003 present')
    patterns = [
        r"(?:roll|student)\s*(\d+)\s*(present|absent)",
        r"(23cse\d{3})\s*(present|absent)"
    ]

    for pat in patterns:
        matches = re.findall(pat, text)
        for num, status in matches:
            roll = num.upper() if "CSE" in num.upper() else f"23CSE{int(num):03d}"
            results.append({
                "roll_number": roll,
                "status": "Present" if status.lower() == "present" else "Absent"
            })

    return results
