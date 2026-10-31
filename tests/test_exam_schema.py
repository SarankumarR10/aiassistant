import sqlite3
import unittest

from exams.schema import ensure_exam_schema


class ExamSchemaTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT NOT NULL)")
        self.connection.execute("CREATE TABLE subjects (id INTEGER PRIMARY KEY, code TEXT NOT NULL)")
        self.connection.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL)")
        ensure_exam_schema(self.connection.cursor())
        self.connection.execute("INSERT INTO users VALUES (1, 'faculty')")
        self.connection.execute("INSERT INTO users VALUES (2, 'student')")
        self.connection.execute("INSERT INTO subjects VALUES (1, 'CS101')")
        self.connection.execute("INSERT INTO students VALUES (1, 2)")

    def tearDown(self):
        self.connection.close()

    def test_exam_questions_and_attempt_are_related(self):
        exam_id = self.connection.execute("""INSERT INTO online_exams
            (faculty_id, subject_id, title, duration_minutes, total_marks, passing_marks)
            VALUES (1, 1, 'Unit Test', 30, 5, 2) RETURNING id""").fetchone()[0]
        question_id = self.connection.execute("""INSERT INTO online_questions
            (faculty_id, subject_id, question_type, prompt, marks, correct_answer)
            VALUES (1, 1, 'mcq', 'Pick A', 5, 'A') RETURNING id""").fetchone()[0]
        self.connection.execute(
            "INSERT INTO online_exam_questions (exam_id, question_id, question_order) VALUES (?, ?, 1)",
            (exam_id, question_id),
        )
        attempt_id = self.connection.execute("""INSERT INTO online_exam_attempts
            (exam_id, student_id, started_at, ends_at) VALUES (?, 1, 100, 1900) RETURNING id""",
            (exam_id,),
        ).fetchone()[0]
        self.connection.execute("""INSERT INTO online_student_answers
            (attempt_id, question_id, answer_json) VALUES (?, ?, '"A"')""", (attempt_id, question_id))
        count = self.connection.execute("""SELECT COUNT(*) FROM online_exam_attempts a
            JOIN online_exam_questions q ON q.exam_id = a.exam_id
            JOIN online_student_answers n ON n.attempt_id = a.id AND n.question_id = q.question_id
            WHERE a.id = ?""", (attempt_id,)).fetchone()[0]
        self.assertEqual(count, 1)

    def test_student_cannot_have_duplicate_exam_attempts(self):
        exam_id = self.connection.execute("""INSERT INTO online_exams
            (faculty_id, subject_id, title, duration_minutes, total_marks, passing_marks)
            VALUES (1, 1, 'Unit Test', 30, 5, 2) RETURNING id""").fetchone()[0]
        values = (exam_id, 1, 100, 1900)
        statement = """INSERT INTO online_exam_attempts (exam_id, student_id, started_at, ends_at)
            VALUES (?, ?, ?, ?)"""
        self.connection.execute(statement, values)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(statement, values)


if __name__ == "__main__":
    unittest.main()
