"""Local camera scanner for signed EduPilot attendance QR tokens."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


def decode_qr_frame(frame, detector=None) -> str:
    """Decode QR text from a BGR OpenCV frame, returning an empty string when absent."""
    import cv2

    detector = detector or cv2.QRCodeDetector()
    decoded, _points, _straight = detector.detectAndDecode(frame)
    return decoded.strip()


class AttendanceQRScannerDialog(QDialog):
    """Show a live camera preview and return scanned text without recording attendance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan Class Attendance Code")
        self.setMinimumSize(600, 470)
        self.scanned_text = ""
        self._capture = None
        self._cv2 = None

        layout = QVBoxLayout(self)
        title = QLabel("Scan the current class code")
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #26323B;")
        layout.addWidget(title)

        self.preview = QLabel("Camera is off. Start the camera when the faculty code is ready.")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(560, 330)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet(
            "background: #263746; color: #FFFFFF; border-radius: 8px; padding: 16px;"
        )
        layout.addWidget(self.preview, 1)

        self.status = QLabel("The camera stays on this device. The scanned token is checked before attendance changes.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #52616B;")
        layout.addWidget(self.status)

        actions = QHBoxLayout()
        self.start_button = QPushButton("Start Camera")
        self.start_button.setProperty("class", "secondary")
        self.start_button.clicked.connect(self.start_camera)
        close_button = QPushButton("Cancel")
        close_button.setProperty("class", "outline")
        close_button.clicked.connect(self.reject)
        actions.addWidget(self.start_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._read_frame)

    def start_camera(self):
        try:
            import cv2
            self._cv2 = cv2
            self._capture = cv2.VideoCapture(0)
            if not self._capture.isOpened():
                self._release_camera()
                self.status.setText("No camera is available. You can cancel and paste the faculty's signed code instead.")
                return
            self.start_button.setEnabled(False)
            self.status.setText("Point the camera at the faculty's current EduPilot QR code.")
            self._timer.start()
        except ImportError:
            self.status.setText("Camera scanning needs OpenCV. You can cancel and paste the faculty's signed code instead.")
        except Exception as error:
            self._release_camera()
            self.status.setText(f"Could not start the camera: {error}")

    def _read_frame(self):
        if not self._capture or not self._capture.isOpened():
            self._release_camera()
            self.status.setText("Camera connection was lost. You can retry or paste the signed code instead.")
            self.start_button.setEnabled(True)
            return
        ok, frame = self._capture.read()
        if not ok or frame is None:
            self.status.setText("Waiting for a camera frame…")
            return
        try:
            decoded = decode_qr_frame(frame)
        except Exception as error:
            self.status.setText(f"Could not read this camera frame: {error}")
            return
        if decoded:
            self.scanned_text = decoded
            self.status.setText("Code scanned. Review it in the attendance field, then choose Record attendance.")
            self.accept()
            return

        rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        height, width, _channels = rgb.shape
        image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888).copy()
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def _release_camera(self):
        self._timer.stop()
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def done(self, result):
        self._release_camera()
        super().done(result)

    def closeEvent(self, event):
        self._release_camera()
        super().closeEvent(event)
