import os
import subprocess
import shutil
import threading
import queue
import re

class VoiceEngine:
    """
    Offline typed-command router with optional Text-To-Speech (TTS).
    """
    def __init__(self):
        self.tts_queue = queue.Queue()
        self.is_listening = False
        self._init_tts()

    def _init_tts(self):
        def tts_worker():
            com_runtime = None
            try:
                if os.name == "nt":
                    import pythoncom
                    pythoncom.CoInitialize()
                    com_runtime = pythoncom
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty('rate', 160)
                while True:
                    text = self.tts_queue.get()
                    if text is None:
                        break
                    engine.say(text)
                    engine.runAndWait()
                    self.tts_queue.task_done()
            except Exception as e:
                print(f"[VoiceEngine] TTS Worker Notice: {e}")
            finally:
                if com_runtime:
                    com_runtime.CoUninitialize()

        self.tts_thread = threading.Thread(target=tts_worker, daemon=True)
        self.tts_thread.start()

    def speak(self, text: str):
        """Queue text to speak asynchronously."""
        print(f"[VCET Assistant Voice]: {text}")
        self.tts_queue.put(text)

    def process_command(self, text: str) -> dict:
        """
        Parses text for wake-words ('Hey VCET Assistant') and intent detection.
        Returns a command dict with status, intent, and message.
        """
        clean_text = text.lower().strip()
        
        # Check wake word
        wake_phrases = ("hey vcet assistant", "hey edupilot assistant", "hey edupilot", "edupilot assistant", "hey vcet", "vcet assistant", "hey assistant")
        has_wake = any(phrase in clean_text for phrase in wake_phrases)
        
        # Strip wake word
        command = clean_text
        for phrase in wake_phrases:
            command = command.replace(phrase, "")
        command = command.strip(" \t,.:;!?-")
        
        if not command and has_wake:
            return {"status": "success", "intent": "greet", "reply": "Hello! I am EduPilot. How can I help you today?"}

        # Match smart lab assistant commands (Feature 6)
        if "open vs code" in command or "open vscode" in command:
            return self._launch_app("code", "VS Code")
        elif "open intellij" in command:
            return self._launch_app("idea64", "IntelliJ IDEA")
        elif "open eclipse" in command:
            return self._launch_app("eclipse", "Eclipse")
        elif "open android studio" in command:
            return self._launch_app("studio64", "Android Studio")
        elif "open sql developer" in command:
            return self._launch_app("sqldeveloper", "SQL Developer")
        elif "open chrome" in command or "open browser" in command:
            return self._launch_app("chrome", "Google Chrome")
        elif "open git bash" in command or "open bash" in command:
            return self._launch_app("git-bash", "Git Bash")
        elif "open powerpoint" in command or "open ppt" in command:
            return self._launch_app("powerpnt", "Microsoft PowerPoint")
        
        # Classroom control (Feature 11)
        elif "next slide" in command:
            return {"status": "success", "intent": "next_slide", "reply": "Moving to next slide."}
        elif "previous slide" in command:
            return {"status": "success", "intent": "prev_slide", "reply": "Moving to previous slide."}
        elif "timer" in command and ("start" in command or "set" in command):
            match = re.search(r"\b(?:start|set)(?:\s+(?:a|the))?\s+timer(?:\s+for)?(?:\s+(\d+)\s+(seconds?|minutes?|hours?))?\b", command)
            if not match:
                return {"status": "error", "intent": "start_timer", "reply": "Use 'start timer' or 'start timer for 5 minutes'."}
            amount = int(match.group(1) or 10)
            unit = (match.group(2) or "minutes").lower()
            multiplier = 3600 if unit.startswith("hour") else (60 if unit.startswith("minute") else 1)
            duration_seconds = amount * multiplier
            if not 1 <= duration_seconds <= 24 * 60 * 60:
                return {"status": "error", "intent": "start_timer", "reply": "Choose a timer duration between 1 second and 24 hours."}
            return {"status": "success", "intent": "start_timer", "duration_seconds": duration_seconds,
                    "reply": f"Starting a {amount} {unit} classroom timer."}
        elif "read today's schedule" in command or "read schedule" in command:
            return {"status": "success", "intent": "read_schedule", "reply": "Reading today's schedule."}
        elif "read announcements" in command or "read notices" in command:
            return {"status": "success", "intent": "read_announcements", "reply": "Reading department announcements."}
        elif "read reminders" in command or "read tasks" in command:
            return {"status": "success", "intent": "read_reminders", "reply": "Reading upcoming reminders."}

        # Code & Compilation (Feature 6, 10)
        elif "run python" in command:
            return {"status": "success", "intent": "run_python", "reply": "Opening the isolated Python code runner."}
        elif "compile java" in command:
            return {"status": "success", "intent": "compile_java", "reply": "Opening the isolated Java code runner."}
        elif "create project" in command:
            return {"status": "success", "intent": "create_project", "reply": "Opening the local project creator."}

        # Fallback query
        return {"status": "success", "intent": "query", "query": command, "reply": f"Processing request: '{command}'"}

    def _launch_app(self, exec_name: str, app_title: str) -> dict:
        return {"status": "confirmation_required", "intent": "launch_app", "app": app_title,
                "executable": exec_name, "reply": f"Open {app_title}?"}

    def launch_confirmed_app(self, executable: str, app_title: str) -> str:
        allowed = {"code", "idea64", "eclipse", "studio64", "sqldeveloper", "chrome", "git-bash", "powerpnt"}
        if executable not in allowed:
            raise ValueError("This application is not on the approved launcher list.")
        path = shutil.which(executable)
        if not path:
            raise FileNotFoundError(f"{app_title} was not found in the system PATH.")
        if os.name == "nt" and path.lower().endswith((".cmd", ".bat")):
            os.startfile(path)
        else:
            subprocess.Popen([path], shell=False, close_fds=True)
        return f"Opened {app_title}."

# Global singleton
voice_engine = VoiceEngine()
