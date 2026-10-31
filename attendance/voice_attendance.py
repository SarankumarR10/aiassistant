"""
Voice-based Backup Attendance.
Allows students or faculty to mark attendance by speaking roll numbers.
"""
import re

_NUMBER_WORDS = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20,
}
_NUMBER_ALTERNATIVES = "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))


def parse_roll_call_response(spoken_text: str) -> str | None:
    """Return a single explicit present/absent response, or None when unclear."""
    statuses = {word.casefold() for word in re.findall(r"\b(present|absent)\b", spoken_text, re.IGNORECASE)}
    if len(statuses) > 1:
        raise ValueError("Say either present or absent for this student, not both.")
    if not statuses:
        return None
    return "Present" if statuses.pop() == "present" else "Absent"


def parse_voice_attendance_phrase(spoken_text: str, students=None) -> list:
    """
    Parses roster names or roll numbers in phrases such as 'Arun Kumar present, Roll 2 absent'.
    Returns list of parsed records: [{'roll_number': '23CSE001', 'status': 'Present'}, ...]
    """
    results = {}
    text = spoken_text.lower()

    # Accept both digits and spoken number words for convenient roll calls.
    patterns = [
        rf"(?:roll(?:\s+number)?|student)\s*#?\s*(\d+|{_NUMBER_ALTERNATIVES})\s*(present|absent)",
        r"([0-9]{2}cse[0-9]{3})\s*(present|absent)"
    ]

    for pat in patterns:
        matches = re.findall(pat, text)
        for num, status in matches:
            if "CSE" in num.upper():
                roll = num.upper()
            else:
                numeric_roll = int(num) if num.isdigit() else _NUMBER_WORDS[num.casefold()]
                roster_match = next((str(row[1]).upper() for row in (students or [])
                                     if re.search(r"(\d+)$", str(row[1]))
                                     and int(re.search(r"(\d+)$", str(row[1])).group(1)) == numeric_roll), None)
                roll = roster_match or f"23CSE{numeric_roll:03d}"
            parsed = "Present" if status.lower() == "present" else "Absent"
            if roll in results and results[roll] != parsed:
                raise ValueError(f"Conflicting attendance statuses were given for {roll}.")
            results[roll] = parsed

    # Recognize names from the selected roster, longest names first to avoid
    # matching a shorter name inside another student's full name.
    for student in sorted(students or [], key=lambda row: len(str(row[2])), reverse=True):
        roll_number, name = str(student[1]), str(student[2]).strip()
        if not name:
            continue
        name_pattern = r"\s+".join(re.escape(part) for part in name.split())
        pattern = rf"(?<!\w){name_pattern}(?!\w)\s*(?:(?:is|marked|as)\s+)?(present|absent)\b"
        for status in re.findall(pattern, text, flags=re.IGNORECASE):
            parsed = "Present" if status.lower() == "present" else "Absent"
            if roll_number in results and results[roll_number] != parsed:
                raise ValueError(f"Conflicting attendance statuses were given for {roll_number}.")
            results[roll_number] = parsed

    return [{"roll_number": roll, "status": status} for roll, status in results.items()]
