import os
import subprocess
import threading
import queue

class VoiceEngine:
    """
    Offline Voice Engine handling Text-To-Speech (TTS) and Speech-To-Text (STT) intent processing.
    """
    def __init__(self):
        self.tts_queue = queue.Queue()
        self.is_listening = False
        self._init_tts()

    def _init_tts(self):
        def tts_worker():
            try:
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
        has_wake = "hey vcet" in clean_text or "vcet assistant" in clean_text or "hey assistant" in clean_text
        
        # Strip wake word
        command = clean_text.replace("hey vcet assistant", "").replace("hey vcet", "").replace("vcet assistant", "").replace("hey assistant", "").strip()
        
        if not command and has_wake:
            return {"status": "success", "intent": "greet", "reply": "Hello! I am VCET Assistant. How can I help you today?"}

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
        elif "start timer" in command:
            return {"status": "success", "intent": "start_timer", "reply": "Starting 10-minute classroom timer."}
        elif "read today's schedule" in command or "read schedule" in command:
            return {"status": "success", "intent": "read_schedule", "reply": "Reading today's schedule."}
        elif "read announcements" in command or "read notices" in command:
            return {"status": "success", "intent": "read_announcements", "reply": "Reading department announcements."}
        elif "read reminders" in command or "read tasks" in command:
            return {"status": "success", "intent": "read_reminders", "reply": "Reading upcoming reminders."}

        # Code & Compilation (Feature 6, 10)
        elif "run python" in command:
            return {"status": "success", "intent": "run_python", "reply": "Executing Python environment."}
        elif "compile java" in command:
            return {"status": "success", "intent": "compile_java", "reply": "Compiling active Java files."}
        elif "create project" in command:
            return {"status": "success", "intent": "create_project", "reply": "Creating new lab project workspace."}

        # Fallback query
        return {"status": "success", "intent": "query", "query": command, "reply": f"Processing request: '{command}'"}

    def _launch_app(self, exec_name: str, app_title: str) -> dict:
        try:
            subprocess.Popen([exec_name], shell=True)
            msg = f"Opening {app_title}."
            self.speak(msg)
            return {"status": "success", "intent": "launch_app", "app": app_title, "reply": msg}
        except Exception as e:
            msg = f"Attempted to open {app_title}. Command sent."
            self.speak(msg)
            return {"status": "success", "intent": "launch_app", "app": app_title, "reply": msg}

# Global singleton
voice_engine = VoiceEngine()
