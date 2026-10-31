"""
Voice and Smart Lab Command Handler mapping natural language inputs to actions.
"""
from database.database import (get_timetables, get_lab_experiments, search_faq,
                               get_announcements, get_reminders, record_assistant_query_event,
                               get_notes)
from datetime import datetime
import re
from difflib import SequenceMatcher


def find_course_materials(query: str, limit: int = 25) -> list[tuple]:
    """Return locally indexed course notes ranked by title, subject, and unit."""
    notes = get_notes()
    terms = set(re.findall(r"[a-z0-9]+", (query or "").casefold())) - {
        "a", "about", "and", "for", "in", "lecture", "lab", "manual", "material",
        "materials", "notes", "note", "of", "on", "open", "the", "to",
    }
    if not terms:
        return notes[:limit]

    ranked = []
    for note in notes:
        searchable = f"{note[1]} {note[2]} unit {note[3]} {note[4]}".casefold()
        tokens = set(re.findall(r"[a-z0-9]+", searchable))
        overlap = len(terms & tokens)
        coverage = overlap / len(terms)
        title_text = f"{note[1]} {note[4]} unit {note[3]}".casefold()
        fuzzy = SequenceMatcher(None, " ".join(sorted(terms)), title_text).ratio()
        score = coverage * 2.0 + fuzzy * 0.5
        if overlap or fuzzy >= 0.22:
            ranked.append((score, note))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [note for _, note in ranked[:limit]]

def execute_voice_intent(intent_data: dict, user_id: int | None = None, role: str | None = None) -> str:
    intent = intent_data.get("intent")
    
    if intent == "launch_app":
        return intent_data.get("reply", "Application launch needs confirmation.")
    
    elif intent == "read_schedule":
        timetables = get_timetables()
        todays = [entry for entry in timetables if entry[3].lower() == datetime.now().strftime("%A").lower()]
        if not todays:
            return "No scheduled classes found for today."
        schedule_str = "Today's schedule: " + ", ".join([f"{t[1]} ({t[2]}) from {t[4]} to {t[5]} in {t[6]}" for t in todays])
        return schedule_str

    elif intent == "read_announcements":
        anns = get_announcements(role)
        if not anns:
            return "No active announcements found."
        return "Latest Announcements: " + "; ".join([f"{a[2]}: {a[3]}" for a in anns[:3]])

    elif intent == "read_reminders":
        if user_id is None:
            return "Sign in to read your personal reminders."
        rems = get_reminders(user_id=user_id)
        if not rems:
            return "You have no upcoming academic reminders."
        return "Upcoming Reminders: " + "; ".join([f"{r[1]} due {r[3]}" for r in rems[:3]])

    elif intent == "open_course_material":
        return "Review the matching course document in the selection window, then confirm to open it."

    elif intent == "next_slide":
        try:
            import pyautogui
            pyautogui.press('right')
            return "Advanced to next slide."
        except Exception:
            return "Slide controls are unavailable on this computer."

    elif intent == "prev_slide":
        try:
            import pyautogui
            pyautogui.press('left')
            return "Returned to previous slide."
        except Exception:
            return "Slide controls are unavailable on this computer."

    elif intent == "start_timer":
        return "Open the voice console to start the requested countdown timer."

    elif intent == "query":
        q = intent_data.get("query", "")
        faqs = search_faq(q)
        if faqs:
            record_assistant_query_event("learning", user_id=user_id)
            return f"Answer for '{faqs[0][1]}': {faqs[0][2]}"
        from ai.rag_engine import rag_engine
        result = rag_engine.query(q, role=role, user_id=user_id)
        return f"{result['answer']}\nSource: {result['source']}"

    if intent in {"run_python", "compile_java"}:
        return "Open the Code Runner page to review the program, then confirm isolated execution there."
    if intent == "create_project":
        return "Open the Code Runner page, choose New Project, then confirm its name, language, and destination."
    return intent_data.get("reply", "I couldn't match that command to an available action.")
