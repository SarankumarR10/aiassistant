"""Qt worker thread wrapper for offline microphone transcription."""
from threading import Event

from PySide6.QtCore import QThread, Signal

from voice.speech_input import listen_for_phrases


class SpeechInputWorker(QThread):
    phrase_recognized = Signal(str)
    partial_text = Signal(str)
    audio_level = Signal(int)
    failed = Signal(str)

    def __init__(self, parent=None, command_mode=False, input_device=None):
        super().__init__(parent)
        self._stop_event = Event()
        self._command_mode = command_mode
        self._input_device = input_device

    def request_stop(self):
        self._stop_event.set()

    def run(self):
        try:
            listen_for_phrases(
                self._stop_event,
                self.phrase_recognized.emit,
                command_mode=self._command_mode,
                on_partial=self.partial_text.emit,
                input_device=self._input_device,
                on_audio_level=self.audio_level.emit,
            )
        except Exception as error:
            self.failed.emit(str(error))
