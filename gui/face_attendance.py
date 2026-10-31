"""Faculty-confirmed face enrollment and candidate matching dialogs."""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from attendance.face_attendance import FaceAttendanceSystem
from database.database import save_student_face_enrollment


def _frame_pixmap(frame, cv2, target: QLabel) -> QPixmap:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(image).scaled(
        target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
    )


def _open_camera(cv2):
    if sys.platform == "win32":
        capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if capture.isOpened():
            return capture
        capture.release()
    return cv2.VideoCapture(0)


class FaceEnrollmentDialog(QDialog):
    """Capture and encrypt local face crops after faculty confirms consent."""

    def __init__(self, student_id: int, student_name: str, faculty_id: int, parent=None):
        super().__init__(parent)
        try:
            from cryptography.fernet import Fernet  # noqa: F401
        except ImportError as error:
            raise RuntimeError(
                "Encrypted face enrollment needs cryptography. Install the optional project requirements and restart EduPilot."
            ) from error
        self.student_id = int(student_id)
        self.student_name = student_name
        self.faculty_id = int(faculty_id)
        self.system = FaceAttendanceSystem()
        self.samples: list[str] = []
        self._frame = None
        self._face_count = 0
        self.capture = _open_camera(self.system.cv2)
        if not self.capture.isOpened():
            self.capture.release()
            raise RuntimeError("Could not open a camera. Connect or enable a webcam, then try again.")
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._update_frame)
        self.timer.start()

    def _build_ui(self):
        self.setWindowTitle("Opt-in face enrollment")
        self.setMinimumSize(600, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Enroll face for {self.student_name}"))
        instructions = QLabel(
            "Center one face in the camera. Capture 5–10 clear samples with small changes in head position. "
            "Only face crops are saved; the original camera frames are discarded."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.preview = QLabel("Starting camera…")
        self.preview.setMinimumSize(480, 300)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: #17232C; color: white; border-radius: 8px;")
        layout.addWidget(self.preview, 1)
        consent_note = QLabel(
            "Enrollment is optional. Encrypted face crops stay on this device and expire after 90 days. "
            "Manual and QR attendance remain available."
        )
        consent_note.setWordWrap(True)
        layout.addWidget(consent_note)
        self.consent = QCheckBox("I confirm this student has opted in to face enrollment.")
        self.consent.toggled.connect(self._update_buttons)
        layout.addWidget(self.consent)
        self.status = QLabel("Confirm opt-in consent before capturing samples.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.capture_button = QPushButton("Capture face sample")
        self.capture_button.setEnabled(False)
        self.capture_button.clicked.connect(self._capture_sample)
        self.save_button = QPushButton("Save encrypted enrollment")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(self.capture_button)
        actions.addWidget(self.save_button)
        actions.addWidget(cancel)
        layout.addLayout(actions)

    def _update_frame(self):
        ok, frame = self.capture.read()
        if not ok:
            self.status.setText("The camera stopped responding. Check the connection and try again.")
            return
        self._frame = frame
        preview, faces = self.system.draw_preview(frame)
        self._face_count = len(faces)
        self.preview.setPixmap(_frame_pixmap(preview, self.system.cv2, self.preview))
        if self.consent.isChecked():
            self.capture_button.setEnabled(len(faces) == 1 and len(self.samples) < 20)

    def _capture_sample(self):
        if not self.consent.isChecked() or self._frame is None:
            return
        try:
            sample = self.system.extract_sample(self._frame)
            self.samples.append(self.system.encode_sample(sample))
        except Exception as error:
            self.status.setText(str(error))
            return
        self.status.setText(f"Captured {len(self.samples)} sample(s). Capture at least 5 before saving.")
        self._update_buttons()

    def _update_buttons(self):
        consented = self.consent.isChecked()
        self.capture_button.setEnabled(
            consented and self._frame is not None and self._face_count == 1 and len(self.samples) < 20
        )
        self.save_button.setEnabled(consented and len(self.samples) >= 5)

    def _save(self):
        if not self.consent.isChecked():
            return
        try:
            expiry = save_student_face_enrollment(
                self.student_id, self.samples, self.faculty_id, consent_confirmed=True
            )
        except Exception as error:
            QMessageBox.critical(self, "Could not save enrollment", str(error))
            return
        self.status.setText(f"Enrollment saved on this device until {expiry[:10]}.")
        self.accept()

    def done(self, result):
        if hasattr(self, "timer"):
            self.timer.stop()
        if hasattr(self, "capture"):
            self.capture.release()
        super().done(result)


class FaceRecognitionDialog(QDialog):
    """Suggest a roster match; require a faculty click before applying it."""

    def __init__(self, system: FaceAttendanceSystem, students: list[tuple], parent=None):
        super().__init__(parent)
        self.system = system
        self.students = {int(row[0]): row for row in students}
        self.candidate_id = None
        self._stable_id = None
        self._stable_frames = 0
        self._frame = None
        self.capture = _open_camera(self.system.cv2)
        if not self.capture.isOpened():
            self.capture.release()
            raise RuntimeError("Could not open a camera. Connect or enable a webcam, then try again.")
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._update_frame)
        self.timer.start()

    def _build_ui(self):
        self.setWindowTitle("Face-assisted attendance")
        self.setMinimumSize(600, 520)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Hold one face in view. A match is only a suggestion; faculty must confirm the student. "
            "This camera check does not detect photos or prove liveness."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.preview = QLabel("Starting camera…")
        self.preview.setMinimumSize(480, 300)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: #17232C; color: white; border-radius: 8px;")
        layout.addWidget(self.preview, 1)
        self.status = QLabel("Waiting for one enrolled face…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.confirm_button = QPushButton("Confirm and mark Present")
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self._confirm)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(self.confirm_button)
        actions.addWidget(cancel)
        layout.addLayout(actions)

    def _update_frame(self):
        ok, frame = self.capture.read()
        if not ok:
            self.status.setText("The camera stopped responding. Check the connection and try again.")
            return
        self._frame = frame
        preview, faces = self.system.draw_preview(frame)
        self.preview.setPixmap(_frame_pixmap(preview, self.system.cv2, self.preview))
        result = self.system.recognize(frame) if len(faces) == 1 else {
            "student_id": None,
            "confidence": None,
            "message": "Show one person at a time." if len(faces) > 1 else "No face detected.",
        }
        candidate = result["student_id"]
        if candidate not in self.students:
            self._stable_id, self._stable_frames = None, 0
            self.confirm_button.setEnabled(False)
            self.status.setText(result["message"])
            return
        if candidate == self._stable_id:
            self._stable_frames += 1
        else:
            self._stable_id, self._stable_frames = candidate, 1
        student = self.students[candidate]
        self.status.setText(
            f"Candidate: {student[2]} ({student[1]}). "
            f"Keep the same face in view to stabilize the match ({min(self._stable_frames, 10)}/10). "
            "Please confirm this is the student."
        )
        self.confirm_button.setEnabled(self._stable_frames >= 10)

    def _confirm(self):
        if self._stable_id in self.students and self._stable_frames >= 10:
            self.candidate_id = self._stable_id
            self.accept()

    def done(self, result):
        if hasattr(self, "timer"):
            self.timer.stop()
        if hasattr(self, "capture"):
            self.capture.release()
        super().done(result)
