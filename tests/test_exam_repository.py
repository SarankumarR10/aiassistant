import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exams.schema import ensure_exam_schema
from exams import repository


class ExamRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="exam-repo-", dir=Path.cwd())
        self.db_path = Path(self.temp.name) / "exam.sqlite3"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT NOT NULL)")
            conn.execute("CREATE TABLE subjects (id INTEGER PRIMARY KEY, code TEXT NOT NULL)")
            conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL)")
            conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            ensure_exam_schema(conn.cursor())
            conn.execute("INSERT INTO users VALUES (1, 'faculty')")
            conn.execute("INSERT INTO users VALUES (2, 'student')")
            conn.execute("INSERT INTO subjects VALUES (1, 'CS101')")
            conn.execute("INSERT INTO students VALUES (1, 2)")
            conn.commit()
        finally:
            conn.close()
        self.connection_patch = patch.object(
            repository, "get_connection", side_effect=lambda: sqlite3.connect(self.db_path)
        )
        self.connection_patch.start()

    def tearDown(self):
        self.connection_patch.stop()
        self.temp.cleanup()

    def test_faculty_authors_publishes_and_previews_mcq_exam(self):
        exam_id = repository.create_exam(1, 1, "Algorithms Quiz", exam_type="MCQ", passing_marks=2)
        question_id = repository.create_question(1, 1, {
            "question_type": "mcq", "prompt": "Which is logarithmic?", "marks": 5,
            "options": [
                {"text": "Binary search", "is_correct": True},
                {"text": "Linear search", "is_correct": False},
            ],
        })
        repository.add_question_to_exam(1, exam_id, question_id)
        self.assertEqual(repository.publish_exam(1, exam_id), 5)
        preview = repository.get_exam_preview(1, exam_id)
        self.assertEqual(preview["exam"]["status"], "published")
        self.assertEqual(preview["questions"][0]["question_type"], "mcq")
        self.assertEqual(preview["questions"][0]["options"][0][2], 1)

    def test_student_cannot_create_exam(self):
        with self.assertRaises(PermissionError):
            repository.create_exam(2, 1, "Unauthorized")

    def test_scheduled_times_require_timezone_and_order(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            repository.create_exam(1, 1, "Bad schedule", starts_at="2026-11-01T09:00:00", ends_at="2026-11-01T10:00:00")
        with self.assertRaisesRegex(ValueError, "after"):
            repository.create_exam(1, 1, "Bad schedule", starts_at="2026-11-01T10:00:00+00:00", ends_at="2026-11-01T09:00:00+00:00")

    def test_publish_requires_questions_and_valid_passing_score(self):
        exam_id = repository.create_exam(1, 1, "Empty Exam", passing_marks=1)
        with self.assertRaisesRegex(ValueError, "at least one question"):
            repository.publish_exam(1, exam_id)

    def test_wrong_question_can_be_removed_from_draft_then_publish_true_false(self):
        exam_id = repository.create_exam(1, 1, "True False Quiz", exam_type="True/False")
        wrong_id = repository.create_question(1, 1, {
            "question_type": "mcq", "prompt": "Old wrong type?", "marks": 1,
            "options": [{"text": "Yes", "is_correct": True}, {"text": "No", "is_correct": False}],
        })
        repository.add_question_to_exam(1, exam_id, wrong_id)
        with self.assertRaisesRegex(ValueError, "different type"):
            repository.publish_exam(1, exam_id)
        repository.remove_question_from_exam(1, exam_id, wrong_id)
        correct_id = repository.create_question(1, 1, {
            "question_type": "True/False", "prompt": "The Earth orbits the Sun.", "marks": 1,
            "options": [{"text": "True", "is_correct": True}, {"text": "False", "is_correct": False}],
        })
        repository.add_question_to_exam(1, exam_id, correct_id)
        self.assertEqual(repository.publish_exam(1, exam_id), 1)


if __name__ == "__main__":
    unittest.main()
