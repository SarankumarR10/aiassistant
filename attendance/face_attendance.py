"""Opt-in, local LBPH face matching for faculty-confirmed attendance suggestions."""
from __future__ import annotations

import base64
from pathlib import Path


class FaceRecognitionUnavailable(RuntimeError):
    """Raised when the OpenCV contrib face recognizer is not installed."""


class FaceAttendanceSystem:
    """Train and match enrolled face samples; never marks attendance by itself."""

    IMAGE_SIZE = (160, 160)

    def __init__(self, confidence_threshold: float = 65.0):
        try:
            import cv2
        except ImportError as error:
            raise FaceRecognitionUnavailable(
                "Face attendance needs OpenCV contrib. Install the optional project requirements and restart EduPilot."
            ) from error
        if not hasattr(cv2, "face") or not hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            raise FaceRecognitionUnavailable(
                "Face identity matching needs opencv-contrib-python. Install the optional project requirements, "
                "then restart EduPilot. If opencv-python is installed, uninstall it before installing opencv-contrib-python."
            )
        self.cv2 = cv2
        cascade_name = "haarcascade_frontalface_default.xml"
        package_cascade = Path(getattr(getattr(cv2, "data", None), "haarcascades", "")) / cascade_name
        project_cascade = Path(__file__).resolve().parents[1] / "assets" / cascade_name
        cascade_path = package_cascade if package_cascade.is_file() else project_cascade
        self.face_cascade = cv2.CascadeClassifier(str(cascade_path))
        if self.face_cascade.empty():
            raise FaceRecognitionUnavailable("The OpenCV face-detection model could not be loaded.")
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.confidence_threshold = float(confidence_threshold)
        self._trained = False

    def detect_faces(self, frame):
        if frame is None:
            return []
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        gray = self.cv2.equalizeHist(gray)
        return list(self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=6, minSize=(75, 75)
        ))

    def extract_sample(self, frame):
        faces = self.detect_faces(frame)
        if len(faces) != 1:
            raise ValueError("Show one face clearly in the camera before capturing a sample.")
        x, y, width, height = faces[0]
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        crop = gray[y:y + height, x:x + width]
        return self._normalize(crop)

    def draw_preview(self, frame):
        preview = frame.copy()
        faces = self.detect_faces(frame)
        for x, y, width, height in faces:
            self.cv2.rectangle(preview, (x, y), (x + width, y + height), (60, 110, 145), 2)
        return preview, faces

    def encode_sample(self, sample) -> str:
        success, encoded = self.cv2.imencode(".png", self._normalize(sample))
        if not success:
            raise RuntimeError("Could not prepare this face sample for local storage.")
        return base64.b64encode(encoded.tobytes()).decode("ascii")

    def decode_sample(self, encoded: str):
        import numpy as np

        raw = base64.b64decode(encoded, validate=True)
        image = self.cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), self.cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("An enrolled face sample could not be read.")
        return self._normalize(image)

    def train(self, enrollments: list[tuple[int, list[str]]]) -> int:
        import numpy as np

        images, labels = [], []
        for student_id, encoded_samples in enrollments:
            if len(encoded_samples) < 5:
                continue
            for encoded in encoded_samples:
                images.append(self.decode_sample(encoded))
                labels.append(int(student_id))
        if not images:
            raise ValueError("No active face enrollments are available for this section on this device.")
        self.recognizer.train(images, np.asarray(labels, dtype=np.int32))
        self._trained = True
        return len(set(labels))

    def recognize(self, frame) -> dict:
        if not self._trained:
            raise RuntimeError("Train the recognizer with active student enrollments first.")
        faces = self.detect_faces(frame)
        if not faces:
            return {"student_id": None, "confidence": None, "message": "No face detected."}
        if len(faces) != 1:
            return {"student_id": None, "confidence": None, "message": "Show only one person at a time."}
        x, y, width, height = faces[0]
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        sample = self._normalize(gray[y:y + height, x:x + width])
        label, confidence = self.recognizer.predict(sample)
        if confidence > self.confidence_threshold:
            return {"student_id": None, "confidence": float(confidence), "message": "No confident enrolled match."}
        return {
            "student_id": int(label),
            "confidence": float(confidence),
            "message": "Candidate match. Faculty must confirm the student before marking attendance.",
        }

    def _normalize(self, gray_face):
        gray_face = self.cv2.resize(gray_face, self.IMAGE_SIZE)
        return self.cv2.equalizeHist(gray_face)
