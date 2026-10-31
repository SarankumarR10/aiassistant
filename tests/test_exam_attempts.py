import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exams import attempts, repository, review
from exams.schema import ensure_exam_schema


class ExamAttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="exam-attempt-", dir=Path.cwd())
        self.db_path = Path(self.temp.name) / "exam.sqlite3"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT NOT NULL)")
            conn.execute("CREATE TABLE subjects (id INTEGER PRIMARY KEY, code TEXT NOT NULL, name TEXT NOT NULL)")
            conn.execute("CREATE TABLE academic_classes (id INTEGER PRIMARY KEY, department TEXT, year_of_study INTEGER, section TEXT, academic_year TEXT)")
            conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, roll_number TEXT, name TEXT, class_id INTEGER)")
            conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            ensure_exam_schema(conn.cursor())
            conn.execute("INSERT INTO users VALUES (1, 'faculty')")
            conn.execute("INSERT INTO users VALUES (2, 'student')")
            conn.execute("INSERT INTO subjects VALUES (1, 'CS101', 'Algorithms')")
            conn.execute("INSERT INTO students (id, user_id, roll_number, name, class_id) VALUES (1, 2, 'CS001', 'Test Student', NULL)")
            conn.commit()
        finally:
            conn.close()
        self.repo_patch = patch.object(repository, "get_connection", side_effect=self.connect)
        self.attempt_patch = patch.object(attempts, "get_connection", side_effect=self.connect)
        self.review_patch = patch.object(review, "get_connection", side_effect=self.connect)
        self.repo_patch.start()
        self.attempt_patch.start()
        self.review_patch.start()
        self.exam_id = repository.create_exam(1, 1, "Quiz", exam_type="MCQ", passing_marks=2)
        self.question_id = repository.create_question(1, 1, {
            "question_type": "mcq", "prompt": "Pick A", "marks": 3,
            "options": [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}],
        })
        repository.add_question_to_exam(1, self.exam_id, self.question_id)
        repository.publish_exam(1, self.exam_id)

    def connect(self):
        return sqlite3.connect(self.db_path)

    def tearDown(self):
        self.attempt_patch.stop()
        self.review_patch.stop()
        self.repo_patch.stop()
        self.temp.cleanup()

    def test_attempt_hides_answer_key_autosaves_and_scores(self):
        attempt = attempts.start_attempt(2, self.exam_id)
        question = attempt["questions"][0]
        self.assertNotIn("correct_answer", question)
        self.assertNotIn("is_correct", question["options"][0])
        attempts.save_answer(2, attempt["id"], self.question_id, 1)
        restored = attempts.get_attempt(2, attempt["id"])
        self.assertEqual(restored["questions"][0]["answer"], 1)
        result = attempts.submit_attempt(2, attempt["id"])
        self.assertEqual(result["marks_awarded"], 3)
        self.assertEqual(result["outcome"], "Pass")
        catalog = attempts.get_student_exam_catalog(2)
        self.assertEqual(catalog[0]["result_outcome"], "Pass")
        self.assertEqual(catalog[0]["result_marks"], 3)

    def test_attempt_is_private_to_owning_student(self):
        attempt = attempts.start_attempt(2, self.exam_id)
        with self.assertRaises(PermissionError):
            attempts.get_attempt(1, attempt["id"])

    def test_expired_attempt_is_auto_submitted_when_student_returns(self):
        with patch.object(attempts.time, "time", return_value=1000):
            attempt = attempts.start_attempt(2, self.exam_id)
        conn = self.connect()
        try:
            conn.execute("UPDATE online_exam_attempts SET ends_at = 1000 WHERE id = ?", (attempt["id"],))
            conn.commit()
        finally:
            conn.close()
        with patch.object(attempts.time, "time", return_value=1000):
            with self.assertRaisesRegex(ValueError, "submitted automatically"):
                attempts.start_attempt(2, self.exam_id)
        conn = self.connect()
        try:
            status = conn.execute("SELECT status FROM online_exam_attempts WHERE id = ?", (attempt["id"],)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(status, "auto_submitted")

    def test_faculty_can_review_and_grade_submitted_descriptive_answer(self):
        exam_id = repository.create_exam(1, 1, "Written Quiz", exam_type="Descriptive", passing_marks=2)
        question_id = repository.create_question(1, 1, {
            "question_type": "descriptive", "prompt": "Explain the idea.", "marks": 4,
        })
        repository.add_question_to_exam(1, exam_id, question_id)
        repository.publish_exam(1, exam_id)
        attempt = attempts.start_attempt(2, exam_id)
        attempts.save_answer(2, attempt["id"], question_id, "My explanation")
        attempts.submit_attempt(2, attempt["id"])

        exams = review.get_submitted_exams(1)
        self.assertEqual(exams[0][0], exam_id)
        attempts_list = review.get_exam_attempts(1, exam_id)
        self.assertEqual(attempts_list[0][0], attempt["id"])
        detail = review.get_attempt_answers(1, attempt["id"])
        self.assertEqual(detail["questions"][0]["answer"], "My explanation")
        result = review.grade_exam_answer(1, attempt["id"], question_id, 3, "Clear response")
        self.assertEqual(result["marks_awarded"], 3)
        self.assertEqual(result["outcome"], "Pass")
        detail = review.get_attempt_answers(1, attempt["id"])
        self.assertEqual(detail["questions"][0]["feedback"], "Clear response")


if __name__ == "__main__":
    unittest.main()
