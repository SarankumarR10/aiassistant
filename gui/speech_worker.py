"""Qt worker thread wrapper for offline microphone transcription."""
from threading import Event

from PySide6.QtCore import QThread, Signal

from voice.speech_input import listen_for_phrases


class SpeechInputWorker(QThread):
    phrase_recognized = Signal(str)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_event = Event()

    def request_stop(self):
        self._stop_event.set()

    def run(self):
        try:
            listen_for_phrases(self._stop_event, self.phrase_recognized.emit)
        except Exception as error:
            self.failed.emit(str(error))
