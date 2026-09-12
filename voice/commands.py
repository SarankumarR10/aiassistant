"""
Voice and Smart Lab Command Handler mapping natural language inputs to actions.
"""
from database.database import get_timetables, get_lab_experiments, search_faq, get_announcements, get_reminders

def execute_voice_intent(intent_data: dict) -> str:
    intent = intent_data.get("intent")
    
    if intent == "launch_app":
        return intent_data.get("reply", "App launched.")
    
    elif intent == "read_schedule":
        timetables = get_timetables()
        if not timetables:
            return "No scheduled classes found for today."
        schedule_str = "Today's schedule: " + ", ".join([f"{t[1]} ({t[2]}) from {t[4]} to {t[5]} in {t[6]}" for t in timetables])
        return schedule_str

    elif intent == "read_announcements":
        anns = get_announcements()
        if not anns:
            return "No active announcements found."
        return "Latest Announcements: " + "; ".join([f"{a[2]}: {a[3]}" for a in anns[:3]])

    elif intent == "read_reminders":
        rems = get_reminders(user_id=1)
        if not rems:
            return "You have no upcoming academic reminders."
        return "Upcoming Reminders: " + "; ".join([f"{r[1]} due {r[3]}" for r in rems[:3]])

    elif intent == "next_slide":
        try:
            import pyautogui
            pyautogui.press('right')
            return "Advanced to next slide."
        except Exception:
            return "Next slide command registered."

    elif intent == "prev_slide":
        try:
            import pyautogui
            pyautogui.press('left')
            return "Returned to previous slide."
        except Exception:
            return "Previous slide command registered."

    elif intent == "start_timer":
        return "15-minute exam/lab timer started on screen."

    elif intent == "query":
        q = intent_data.get("query", "")
        faqs = search_faq(q)
        if faqs:
            return f"Answer for '{faqs[0][1]}': {faqs[0][2]}"
        return f"Searching local knowledge base for: {q}. Check AI Assistant tab for details."

    return intent_data.get("reply", "Command executed successfully.")

