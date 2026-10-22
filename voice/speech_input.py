"""Optional offline microphone transcription using a local Vosk model."""
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = PROJECT_ROOT / "models" / "vosk-model-small-en-us-0.15"

_COMMAND_HINTS = (
    ("open", "vs code"), ("open", "vs", "code"), ("open", "vscode"),
    ("open", "us", "code"), ("open", "this", "code"), ("open", "west", "coast"),
    ("open", "code"), ("open", "intellij"),
    ("open", "eclipse"), ("open", "chrome"), ("open", "browser"),
    ("open", "android studio"), ("open", "sql developer"),
    ("open", "git bash"), ("open", "powerpoint"), ("next", "slide"),
    ("previous", "slide"), ("timer",), ("read", "schedule"),
    ("read", "announcement"), ("read", "notice"), ("read", "reminder"),
    ("read", "task"), ("run", "python"), ("compile", "java"),
    ("create", "project"),
)

_COMMAND_GRAMMAR = [
    "open vs code", "open v s code", "open visual studio code", "open vscode",
    "open us code", "open this code", "open the score", "open code",
    "open intellij", "open eclipse", "open android studio", "open sql developer",
    "open chrome", "open browser", "open git bash", "open powerpoint",
    "next slide", "previous slide", "start timer", "start timer for one minute",
    "start timer for five minutes", "set a timer for five minutes", "read schedule",
    "read today's schedule", "read announcements", "read notices", "read reminders",
    "read tasks", "run python", "compile java", "create project", "[unk]",
]


def _recognized_text(result: str, command_mode: bool) -> str:
    """Pick the strongest Vosk alternative, preferring candidates matching known commands."""
    payload = json.loads(result)
    alternatives = payload.get("alternatives")
    if not alternatives:
        return payload.get("text", "").strip()
    if not command_mode:
        return str(alternatives[0].get("text", "")).strip()

    def rank(item):
        text = str(item.get("text", "")).lower()
        words = set(text.split())
        hint_score = max((len(hint) for hint in _COMMAND_HINTS if all(word in words or " ".join(hint) in text for word in hint)), default=0)
        confidence = float(item.get("confidence", 0.0))
        return (hint_score, confidence)

    return str(max(alternatives, key=rank).get("text", "")).strip()


def _model_path() -> Path:
    configured = os.environ.get("EDUPILOT_VOSK_MODEL", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_MODEL


def speech_input_status() -> tuple[bool, str]:
    """Return whether offline speech capture is configured and a user-facing explanation."""
    model = _model_path()
    if not model.is_dir():
        return False, (
            "Offline microphone input is not configured. Install sounddevice and place a Vosk English model in "
            f"{DEFAULT_MODEL.relative_to(PROJECT_ROOT)}, or set EDUPILOT_VOSK_MODEL to its folder."
        )
    try:
        import vosk  # noqa: F401
    except ImportError:
        return False, "Offline microphone input needs Vosk. Install the project dependencies and restart EduPilot."
    try:
        import sounddevice  # noqa: F401
    except ImportError:
        return False, "Offline microphone input needs sounddevice. Install the project dependencies and restart EduPilot."
    return True, f"Offline microphone ready · {model.name}"


def listen_for_phrases(stop_event: Event, on_phrase, command_mode: bool = False) -> None:
    """Capture microphone audio and emit complete recognized phrases until stopped."""
    ready, explanation = speech_input_status()
    if not ready:
        raise RuntimeError(explanation)

    import sounddevice as sd
    import vosk

    model = vosk.Model(str(_model_path()))
    recognizer = vosk.KaldiRecognizer(model, 16_000)
    command_recognizer = None
    if command_mode:
        recognizer.SetMaxAlternatives(5)
        try:
            command_recognizer = vosk.KaldiRecognizer(
                model, 16_000, json.dumps(_COMMAND_GRAMMAR)
            )
            command_recognizer.SetMaxAlternatives(5)
        except Exception:
            # Keep unrestricted offline transcription available if this Vosk model
            # does not support dynamic phrase grammars.
            command_recognizer = None
    audio_blocks: Queue[bytes] = Queue(maxsize=24)

    def receive_audio(indata, frames, timing, status):
        if status:
            return
        block = bytes(indata)
        try:
            audio_blocks.put_nowait(block)
        except Full:
            try:
                audio_blocks.get_nowait()
            except Empty:
                pass
            try:
                audio_blocks.put_nowait(block)
            except Full:
                pass

    try:
        with sd.RawInputStream(samplerate=16_000, blocksize=8_000, channels=1,
                               dtype="int16", callback=receive_audio):
            general_result = None
            grammar_result = None
            while not stop_event.is_set():
                try:
                    audio = audio_blocks.get(timeout=0.2)
                except Empty:
                    continue
                general_done = recognizer.AcceptWaveform(audio)
                grammar_done = command_recognizer.AcceptWaveform(audio) if command_recognizer else False
                if general_done:
                    general_result = _recognized_text(recognizer.Result(), command_mode)
                if grammar_done:
                    grammar_result = _recognized_text(command_recognizer.Result(), True)

                # Wait until both decoders have finalized the same phrase. Prefer
                # a known command from the constrained decoder; use unrestricted
                # speech when it reports [unk] so course questions still work.
                if general_result is not None and (grammar_result is not None or not command_recognizer):
                    grammar_text = (grammar_result or "").replace("[unk]", "").strip()
                    phrase = grammar_text or general_result
                    general_result = None
                    grammar_result = None
                    if phrase:
                        on_phrase(phrase)
                        if command_mode:
                            stop_event.set()
            general_text = _recognized_text(recognizer.FinalResult(), command_mode)
            grammar_text = ""
            if command_recognizer:
                grammar_text = _recognized_text(command_recognizer.FinalResult(), True).replace("[unk]", "").strip()
            final_phrase = grammar_text or general_text
            if final_phrase:
                on_phrase(final_phrase)
    except Exception as error:
        if stop_event.is_set():
            return
        raise RuntimeError(f"Microphone transcription stopped: {error}") from error
