"""Detection-only camera helper. Detection cannot verify a student's identity."""
import cv2


class FaceAttendanceSystem:
    def __init__(self):
        try:
            cascade = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.face_cascade = cv2.CascadeClassifier(cascade)
        except Exception:
            self.face_cascade = None

    def detect_and_recognize(self, frame):
        """Draw face boxes for diagnostics; always returns zero verified students."""
        if frame is None or self.face_cascade is None or self.face_cascade.empty():
            return frame, []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        for x, y, w, h in faces:
            color = (40, 120, 180)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, "Identity not verified", (x, max(20, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame, []
