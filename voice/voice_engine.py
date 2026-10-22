import os
import subprocess
import shutil
import threading
import queue
import re
from difflib import SequenceMatcher
from pathlib import Path


_NUMBER_WORDS = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}


def _spoken_number(value: str) -> int | None:
    value = value.strip().lower().replace("-", " ")
    if value.isdigit():
        return int(value)
    total = 0
    current = 0
    for word in value.split():
        if word == "and":
            continue
        if word == "hundred":
            current = max(current, 1) * 100
        elif word in _NUMBER_WORDS:
            current += _NUMBER_WORDS[word]
        else:
            return None
    return total + current if current else None


def _normalize_voice_text(text: str) -> str:
    """Normalize common Vosk variants of short, known EduPilot voice commands."""
    clean = text.lower().strip()
    clean = clean.replace("e du pilot", "edupilot").replace("eddy pilot", "edupilot")
    clean = re.sub(r"\bvisual studio code\b", "vs code", clean)
    clean = re.sub(r"\bv\s+s\s+code\b", "vs code", clean)
    clean = re.sub(r"\b(vs|us|this|west|yes|the)\s+(code|coat|go|score|cold)\b", "vs code", clean)
    clean = re.sub(r"\b(read|show)\s+me\s+(the\s+)?schedule\b", "read schedule", clean)
    clean = re.sub(r"\b(read|show)\s+(the\s+)?announcements?\b", "read announcements", clean)
    clean = re.sub(r"\b(read|show)\s+(the\s+)?notices?\b", "read notices", clean)
    clean = re.sub(r"\b(read|show)\s+(my\s+)?reminders?\b", "read reminders", clean)
    clean = re.sub(r"\bnext slides?\b", "next slide", clean)
    clean = re.sub(r"\b(previous|prior) slides?\b", "previous slide", clean)
    clean = re.sub(r"^(please\s+|could you\s+|can you\s+)+", "", clean)

    app_request = re.search(r"\b(open|launch|start)\s+(.+)$", clean)
    if app_request:
        target = re.sub(r"\b(the|please|application|editor)\b", " ", app_request.group(2))
        target = re.sub(r"[^a-z0-9]+", " ", target).strip()
        compact = target.replace(" ", "")
        aliases = ("vscode", "vscoad", "uscode", "thiscode", "westcoast", "yescode", "score", "code")
        if max(SequenceMatcher(None, compact, alias).ratio() for alias in aliases) >= 0.75:
            clean = f"{app_request.group(1)} vs code"
    return clean

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
        clean_text = _normalize_voice_text(text)
        
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
            match = re.search(
                r"\b(\d+|(?:zero|oh|one|two|three|four|five|six|seven|eight|nine|ten|"
                r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
                r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|and)(?:[ -]+(?:zero|oh|one|two|three|four|five|six|seven|eight|nine|ten|"
                r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
                r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|and))*)\s+"
                r"(seconds?|minutes?|hours?)\b",
                command,
            )
            if match:
                amount = _spoken_number(match.group(1))
                unit = match.group(2).lower()
            else:
                amount, unit = 10, "minutes"
            if amount is None:
                return {"status": "error", "intent": "start_timer", "reply": "I couldn't hear the timer duration. Try 'start timer for five minutes'."}
            multiplier = 3600 if unit.startswith("hour") else (60 if unit.startswith("minute") else 1)
            duration_seconds = amount * multiplier
            if not 1 <= duration_seconds <= 24 * 60 * 60:
                return {"status": "error", "intent": "start_timer", "reply": "Choose a timer duration between 1 second and 24 hours."}
            return {"status": "success", "intent": "start_timer", "duration_seconds": duration_seconds,
                    "reply": f"Starting a {amount} {unit} classroom timer."}
        elif "read schedule" in command or ("schedule" in command and "read" in command):
            return {"status": "success", "intent": "read_schedule", "reply": "Reading today's schedule."}
        elif ("announcement" in command and "read" in command) or ("notice" in command and "read" in command):
            return {"status": "success", "intent": "read_announcements", "reply": "Reading department announcements."}
        elif ("reminder" in command and "read" in command) or ("task" in command and "read" in command):
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
        if not path and executable == "code" and os.name == "nt":
            install_roots = [
                os.environ.get("LOCALAPPDATA", ""),
                os.environ.get("ProgramFiles", r"C:\Program Files"),
                os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            ]
            candidates = [
                Path(root) / "Programs" / "Microsoft VS Code" / "Code.exe"
                if root == os.environ.get("LOCALAPPDATA", "")
                else Path(root) / "Microsoft VS Code" / "Code.exe"
                for root in install_roots if root
            ]
            path = next((str(candidate) for candidate in candidates if candidate.is_file()), None)
        if not path:
            if executable == "code":
                raise FileNotFoundError(
                    "VS Code was not found. Install Visual Studio Code, or add its Code executable to PATH."
                )
            raise FileNotFoundError(f"{app_title} was not found in the system PATH.")
        if os.name == "nt" and path.lower().endswith((".cmd", ".bat")):
            os.startfile(path)
        else:
            subprocess.Popen([path], shell=False, close_fds=True)
        return f"Opened {app_title}."

# Global singleton
voice_engine = VoiceEngine()
