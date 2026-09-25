"""Private, local-first notes with optional offline dictation."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox, QSplitter,
)

from database.database import delete_voice_note, get_voice_notes, save_voice_note
from gui.speech_worker import SpeechInputWorker
from gui.theme import POSITIVUS_QSS, create_section_header
from voice.speech_input import speech_input_status


class VoiceNotesWidget(QWidget):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.notes_by_id = {}
        self.selected_note_id = None
        self.speech_worker = None
        self.speech_error = ""
        self.setStyleSheet(POSITIVUS_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(create_section_header(
            "Private Voice Notes", "Write a note or dictate offline; nothing is shared with other accounts."
        ))

        self.privacy_label = QLabel("Notes are saved on this device under your signed-in account.")
        self.privacy_label.setWordWrap(True)
        self.privacy_label.setStyleSheet("color: #52616B;")
        layout.addWidget(self.privacy_label)

        splitter = QSplitter(Qt.Horizontal)
        self.notes_list = QListWidget()
        self.notes_list.setMinimumWidth(190)
        self.notes_list.setMaximumWidth(320)
        self.notes_list.itemSelectionChanged.connect(self._select_note)
        splitter.addWidget(self.notes_list)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(8, 0, 0, 0)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Note title")
        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("Write a private note or use offline dictation…")
        editor_layout.addWidget(self.title_input)
        editor_layout.addWidget(self.content_input, 1)

        self.dictation_status = QLabel()
        self.dictation_status.setWordWrap(True)
        self.mic_start = QPushButton("Dictate Offline")
        self.mic_start.setProperty("class", "outline")
        self.mic_stop = QPushButton("Stop Dictation")
        self.mic_stop.setProperty("class", "outline")
        self.mic_stop.setEnabled(False)
        ready, explanation = speech_input_status()
        self.mic_start.setEnabled(ready)
        self.dictation_status.setText(explanation)
        self.mic_start.setToolTip(explanation if not ready else "Transcribe through your configured local Vosk model.")
        self.mic_start.clicked.connect(self.start_dictation)
        self.mic_stop.clicked.connect(self.stop_dictation)
        mic_row = QHBoxLayout()
        mic_row.addWidget(self.mic_start)
        mic_row.addWidget(self.mic_stop)
        mic_row.addWidget(self.dictation_status, 1)
        editor_layout.addLayout(mic_row)

        actions = QHBoxLayout()
        self.new_button = QPushButton("New Note")
        self.new_button.setProperty("class", "outline")
        self.new_button.clicked.connect(self.new_note)
        self.save_button = QPushButton("Save Note")
        self.save_button.setProperty("class", "secondary")
        self.save_button.clicked.connect(self.save_note)
        self.delete_button = QPushButton("Delete Note")
        self.delete_button.setProperty("class", "danger")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_note)
        actions.addWidget(self.new_button)
        actions.addStretch()
        actions.addWidget(self.delete_button)
        actions.addWidget(self.save_button)
        editor_layout.addLayout(actions)

        splitter.addWidget(editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        self.load_notes()

    def load_notes(self, select_id=None):
        self.notes_by_id = {row[0]: row for row in get_voice_notes(self.user[0])}
        self.notes_list.blockSignals(True)
        self.notes_list.clear()
        for note_id, title, _content, _created, updated in self.notes_by_id.values():
            item = QListWidgetItem(f"{title}\nUpdated {updated}")
            item.setData(Qt.UserRole, note_id)
            item.setToolTip(title)
            self.notes_list.addItem(item)
            if note_id == select_id:
                self.notes_list.setCurrentItem(item)
        self.notes_list.blockSignals(False)
        if select_id in self.notes_by_id:
            self.selected_note_id = select_id
            self._display_note(self.notes_by_id[select_id])
        else:
            self.selected_note_id = None
            if self.notes_by_id:
                self.notes_list.setCurrentRow(0)
                self._select_note()
            else:
                self._clear_editor()

    def _select_note(self):
        item = self.notes_list.currentItem()
        if item is None:
            return
        note_id = item.data(Qt.UserRole)
        note = self.notes_by_id.get(note_id)
        if note:
            self.selected_note_id = note_id
            self._display_note(note)

    def _display_note(self, note):
        note_id, title, content, _created, _updated = note
        self.selected_note_id = note_id
        self.title_input.setText(title)
        self.content_input.setPlainText(content)
        self.delete_button.setEnabled(True)

    def _clear_editor(self):
        self.selected_note_id = None
        self.title_input.clear()
        self.content_input.clear()
        self.notes_list.clearSelection()
        self.delete_button.setEnabled(False)

    def new_note(self):
        self.notes_list.clearSelection()
        self._clear_editor()
        self.title_input.setFocus()

    def save_note(self):
        try:
            note_id = save_voice_note(
                self.user[0], self.title_input.text(), self.content_input.toPlainText(),
                self.selected_note_id,
            )
        except (ValueError, PermissionError) as error:
            QMessageBox.warning(self, "Could not save note", str(error))
            return
        self.load_notes(note_id)
        self.privacy_label.setText("Note saved locally to your private account notes.")

    def delete_note(self):
        if self.selected_note_id is None:
            return
        answer = QMessageBox.question(
            self, "Delete private note", "Delete this note from your account? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            delete_voice_note(self.user[0], self.selected_note_id)
        except PermissionError as error:
            QMessageBox.warning(self, "Could not delete note", str(error))
            return
        self.load_notes()
        self.privacy_label.setText("Note deleted from your private account notes.")

    def start_dictation(self):
        if self.speech_worker and self.speech_worker.isRunning():
            return
        ready, explanation = speech_input_status()
        if not ready:
            self.dictation_status.setText(explanation)
            return
        self.speech_error = ""
        self.speech_worker = SpeechInputWorker(self)
        self.speech_worker.phrase_recognized.connect(self._append_transcription)
        self.speech_worker.failed.connect(self._dictation_failed)
        self.speech_worker.finished.connect(self._dictation_finished)
        self.mic_start.setEnabled(False)
        self.mic_stop.setEnabled(True)
        self.dictation_status.setText("Listening offline. Pause between phrases; transcript stays on this device.")
        self.speech_worker.start()

    def _append_transcription(self, phrase):
        existing = self.content_input.toPlainText().rstrip()
        self.content_input.setPlainText(f"{existing}\n{phrase}".strip() if existing else phrase)
        cursor = self.content_input.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.content_input.setTextCursor(cursor)

    def _dictation_failed(self, message):
        self.speech_error = message

    def _dictation_finished(self):
        ready, explanation = speech_input_status()
        self.mic_start.setEnabled(ready)
        self.mic_stop.setEnabled(False)
        self.dictation_status.setText(self.speech_error or ("Dictation stopped." if ready else explanation))

    def stop_dictation(self):
        if self.speech_worker and self.speech_worker.isRunning():
            self.dictation_status.setText("Stopping dictation…")
            self.mic_stop.setEnabled(False)
            self.speech_worker.request_stop()

    def closeEvent(self, event):
        if self.speech_worker and self.speech_worker.isRunning():
            self.speech_worker.request_stop()
            self.speech_worker.wait()
        super().closeEvent(event)
