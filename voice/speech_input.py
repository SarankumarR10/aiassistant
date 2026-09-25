"""Optional offline microphone transcription using a local Vosk model."""
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = PROJECT_ROOT / "models" / "vosk-model-small-en-us-0.15"


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


def listen_for_phrases(stop_event: Event, on_phrase) -> None:
    """Capture microphone audio and emit complete recognized phrases until stopped."""
    ready, explanation = speech_input_status()
    if not ready:
        raise RuntimeError(explanation)

    import sounddevice as sd
    import vosk

    model = vosk.Model(str(_model_path()))
    recognizer = vosk.KaldiRecognizer(model, 16_000)
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
            while not stop_event.is_set():
                try:
                    audio = audio_blocks.get(timeout=0.2)
                except Empty:
                    continue
                if recognizer.AcceptWaveform(audio):
                    phrase = json.loads(recognizer.Result()).get("text", "").strip()
                    if phrase:
                        on_phrase(phrase)
            final_phrase = json.loads(recognizer.FinalResult()).get("text", "").strip()
            if final_phrase:
                on_phrase(final_phrase)
    except Exception as error:
        if stop_event.is_set():
            return
        raise RuntimeError(f"Microphone transcription stopped: {error}") from error
