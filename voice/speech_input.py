"""Optional offline microphone transcription using a local Vosk model."""
import json
import math
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
    ("read", "task"), ("open", "notes"), ("open", "manual"),
    ("open", "materials"), ("run", "python"), ("compile", "java"),
    ("create", "project"), ("search", "file"), ("search", "app"),
    ("find", "file"), ("find", "app"), ("search", "for"),
)

_COMMAND_GRAMMAR = [
    "open vs code", "open v s code", "open v s c", "open visual studio code", "open vscode",
    "open vs code editor", "open visual studio", "open us code", "open this code",
    "open west coast", "open the score", "open vsc", "open vscod", "open code",
    "launch vs code", "start vs code",
    "open intellij", "open eclipse", "open android studio", "open sql developer",
    "open notes", "open lecture notes", "open lab manual", "open course materials",
    "open chrome", "open browser", "open git bash", "open powerpoint",
    "next slide", "go to next slide", "previous slide", "go to previous slide",
    "start timer", "start timer for one minute",
    "start timer for five minutes", "set a timer for five minutes", "read schedule",
    "read today's schedule", "read announcements", "read notices", "read reminders",
    "read tasks", "run python", "compile java", "create project", "[unk]",
    "search for files", "search for apps", "search for file", "search for app",
    "find file", "find app", "find application", "search my computer for",
]


def _recognized_text(result: str, command_mode: bool) -> str:
    """Pick the strongest Vosk alternative, preferring candidates matching known commands."""
    payload = json.loads(result)
    alternatives = payload.get("alternatives")
    if not alternatives:
        return str(payload.get("text") or payload.get("partial") or "").strip()
    if not command_mode:
        return str(alternatives[0].get("text", "")).strip()

    def rank(item):
        text = str(item.get("text", "")).lower()
        words = set(text.split())
        hint_score = max((len(hint) for hint in _COMMAND_HINTS if all(word in words or " ".join(hint) in text for word in hint)), default=0)
        confidence = float(item.get("confidence", 0.0))
        return (hint_score, confidence)

    return str(max(alternatives, key=rank).get("text", "")).strip()


def _prefer_command_transcript(grammar_text: str, general_text: str) -> str:
    """Keep free-form search names from being clipped by the command grammar."""
    grammar_text = (grammar_text or "").replace("[unk]", "").strip()
    general_text = (general_text or "").strip()
    if grammar_text.casefold().startswith(("search ", "find ", "open file ", "open app ")):
        if len(general_text.split()) > len(grammar_text.split()):
            return general_text
    return grammar_text or general_text


def _model_path() -> Path:
    configured = os.environ.get("EDUPILOT_VOSK_MODEL", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_MODEL


def list_input_devices() -> list[dict]:
    """List available microphones without exposing backend details to the UI."""
    try:
        import sounddevice as sd
        default = sd.default.device[0]
        default = int(default) if default is not None and int(default) >= 0 else None
        devices = []
        for index, info in enumerate(sd.query_devices()):
            if int(info.get("max_input_channels", 0)) > 0:
                devices.append({
                    "id": index,
                    "name": str(info.get("name") or f"Microphone {index}"),
                    "default": index == default,
                    "sample_rate": int(round(float(info.get("default_samplerate") or 16_000))),
                })
        return devices
    except Exception:
        return []


def speech_input_status(device_id: int | None = None) -> tuple[bool, str]:
    """Return whether offline speech capture is configured and a user-facing explanation."""
    model = _model_path()
    if not model.is_dir():
        return False, (
            "Microphone dictation is not set up yet. Install the optional speech support files, then restart EduPilot."
        )
    try:
        import vosk  # noqa: F401
    except ImportError:
        return False, "Speech recognition is unavailable. Install the optional speech support files, then restart EduPilot."
    try:
        import sounddevice
    except ImportError:
        return False, "Microphone access is unavailable. Install the optional speech support files, then restart EduPilot."
    try:
        device = sounddevice.query_devices(device_id, "input") if device_id is not None else sounddevice.query_devices(kind="input")
        if int(device.get("max_input_channels", 0)) < 1:
            return False, "No microphone input device is enabled. Connect or enable a microphone, then restart EduPilot."
    except Exception as error:
        return False, f"EduPilot cannot access a microphone input device: {error}"
    return True, "Microphone ready for offline dictation and voice commands."


def _resample_to_vosk(audio: bytes, source_rate: int) -> bytes:
    """Resample mono int16 microphone audio to the 16 kHz expected by Vosk."""
    if source_rate == 16_000:
        return audio
    import numpy as np

    samples = np.frombuffer(audio, dtype=np.int16)
    if samples.size < 2:
        return b""
    # A basic linear resampler aliases high-frequency microphone noise when
    # reducing common 44.1/48 kHz device rates. Prefer polyphase filtering.
    try:
        from scipy.signal import resample_poly
        divisor = math.gcd(source_rate, 16_000)
        converted = resample_poly(samples.astype(np.float32), 16_000 // divisor,
                                  source_rate // divisor)
        return np.clip(np.rint(converted), -32768, 32767).astype(np.int16).tobytes()
    except ImportError:
        pass
    divisor = source_rate // 16_000 if source_rate % 16_000 == 0 else 0
    if divisor > 1:
        usable = samples.size - samples.size % divisor
        if usable >= divisor:
            averaged = samples[:usable].astype(np.int32).reshape(-1, divisor).mean(axis=1)
            return np.clip(np.rint(averaged), -32768, 32767).astype(np.int16).tobytes()
    # 44.1 kHz is common on built-in microphones and is not an integer
    # multiple of 16 kHz. Low-pass before interpolation to reduce aliasing.
    ratio = source_rate / 16_000
    taps = max(5, int(math.ceil(ratio)) * 2 + 1)
    if taps % 2 == 0:
        taps += 1
    offsets = np.arange(taps, dtype=np.float64) - taps // 2
    kernel = np.sinc(offsets / ratio) * np.blackman(taps)
    kernel /= kernel.sum()
    filtered = np.convolve(samples.astype(np.float64), kernel, mode="same")
    target_size = max(1, round(samples.size * 16_000 / source_rate))
    source_positions = np.arange(samples.size, dtype=np.float64)
    target_positions = np.linspace(0, samples.size - 1, target_size)
    return np.clip(np.rint(np.interp(target_positions, source_positions, filtered)),
                   -32768, 32767).astype(np.int16).tobytes()


def _prepare_audio(audio: bytes, current_gain: float = 1.0) -> tuple[bytes, int, float]:
    """Measure signal level and gently lift quiet speech without boosting silence."""
    import numpy as np

    samples = np.frombuffer(audio, dtype=np.int16)
    if samples.size == 0:
        return audio, 0, current_gain
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    level = 0 if rms < 90 else min(100, round(rms / 5000 * 100))
    if rms < 90:
        current_gain = max(1.0, current_gain * 0.85)
        return np.zeros_like(samples).tobytes(), level, current_gain

    desired_gain = min(3.5, 1800.0 / max(rms, 1.0)) if rms < 1800 else 1.0
    # Smooth gain changes across short audio blocks to avoid pumping.
    current_gain += (desired_gain - current_gain) * (0.25 if desired_gain > current_gain else 0.12)
    amplified = np.clip(samples.astype(np.float32) * current_gain, -32768, 32767)
    return np.rint(amplified).astype(np.int16).tobytes(), level, current_gain


def listen_for_phrases(stop_event: Event, on_phrase, command_mode: bool = False,
                       on_partial=None, input_device: int | None = None,
                       on_audio_level=None) -> None:
    """Capture microphone audio and emit complete recognized phrases until stopped."""
    ready, explanation = speech_input_status(input_device)
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
    try:
        if input_device is None:
            input_device = sd.default.device[0]
            if input_device is not None and int(input_device) < 0:
                input_device = None
        device_info = sd.query_devices(input_device, "input") if input_device is not None else sd.query_devices(kind="input")
        source_rate = int(round(float(device_info.get("default_samplerate") or 16_000)))
        input_channels = 1
        if int(device_info.get("max_input_channels", 0)) < input_channels:
            raise RuntimeError("The selected microphone has no input channels.")
    except Exception as error:
        raise RuntimeError(f"Could not find an enabled microphone: {error}") from error

    audio_blocks: Queue[bytes] = Queue(maxsize=24)

    def receive_audio(indata, frames, timing, status):
        # Keep the audio block even if PortAudio reports an occasional overflow;
        # discarding all flagged blocks can make the transcript appear blank.
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
        block_size = max(1, int(source_rate * 0.25))
        with sd.RawInputStream(samplerate=source_rate, blocksize=block_size, channels=input_channels,
                               dtype="int16", device=input_device, callback=receive_audio):
            general_result = None
            grammar_result = None
            last_partial = ""
            command_emitted = False
            adaptive_gain = 1.0
            while not stop_event.is_set():
                try:
                    audio = audio_blocks.get(timeout=0.2)
                except Empty:
                    continue
                audio = _resample_to_vosk(audio, source_rate)
                audio, level, adaptive_gain = _prepare_audio(audio, adaptive_gain)
                if on_audio_level:
                    on_audio_level(level)
                general_done = recognizer.AcceptWaveform(audio)
                grammar_done = command_recognizer.AcceptWaveform(audio) if command_recognizer else False
                if general_done:
                    general_result = _recognized_text(recognizer.Result(), command_mode)
                if grammar_done:
                    grammar_result = _recognized_text(command_recognizer.Result(), True)
                if on_partial and not general_done:
                    partial = _recognized_text(recognizer.PartialResult(), command_mode)
                    if partial and partial != last_partial:
                        last_partial = partial
                        on_partial(partial)

                # Wait until both decoders have finalized the same phrase. Prefer
                # a known command from the constrained decoder; use unrestricted
                # speech when it reports [unk] so course questions still work.
                if general_result is not None and (grammar_result is not None or not command_recognizer):
                    phrase = _prefer_command_transcript(grammar_result, general_result)
                    general_result = None
                    grammar_result = None
                    if phrase:
                        on_phrase(phrase)
                        if on_partial:
                            on_partial("")
                        last_partial = ""
                        if command_mode:
                            command_emitted = True
                            stop_event.set()
                            break
            if not command_emitted:
                general_text = _recognized_text(recognizer.FinalResult(), command_mode)
                grammar_text = ""
                if command_recognizer:
                    grammar_text = _recognized_text(command_recognizer.FinalResult(), True)
                final_phrase = _prefer_command_transcript(grammar_text, general_text)
                if final_phrase:
                    on_phrase(final_phrase)
                if on_partial:
                    on_partial("")
    except Exception as error:
        if stop_event.is_set():
            return
        raise RuntimeError(f"Microphone transcription stopped: {error}") from error
