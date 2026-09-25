"""Persistent, timed practical exam sessions for local student accounts."""
import time

from database.database import get_lab_exams, get_connection, _audit


class LabExamAssistant:
    def get_active_exam(self) -> dict | None:
        exams = get_lab_exams()
        if not exams:
            return None
        row = exams[0]
        return {"id": row[0], "subject_code": row[1], "subject_name": row[2],
                "title": row[3], "question_paper": row[4], "duration_minutes": row[5]}

    def start_exam(self, exam_id: int, user_id: int) -> int:
        """Start once, or resume with the original deadline; return seconds remaining."""
        conn = get_connection()
        try:
            exam = conn.execute("SELECT duration_minutes FROM lab_exams WHERE id = ? AND is_active = 1", (exam_id,)).fetchone()
            student = conn.execute("SELECT st.id FROM students st JOIN users u ON u.id = st.user_id WHERE st.user_id = ? AND u.role = 'student'", (user_id,)).fetchone()
            if not exam or not student:
                raise ValueError("This exam or student account is not available.")
            student_id = student[0]
            now = int(time.time())
            row = conn.execute("SELECT expires_at, submitted_at FROM lab_exam_submissions WHERE exam_id = ? AND student_id = ?", (exam_id, student_id)).fetchone()
            if row and row[1]:
                raise ValueError("You have already submitted this exam.")
            if row and row[0] is not None:
                expires_at = row[0]
            else:
                expires_at = now + max(1, int(exam[0] or 60)) * 60
                conn.execute("""INSERT INTO lab_exam_submissions (exam_id, student_id, solution_code, expires_at)
                    VALUES (?, ?, '', ?) ON CONFLICT(exam_id, student_id) DO UPDATE SET expires_at = excluded.expires_at""",
                    (exam_id, student_id, expires_at))
                _audit(conn.cursor(), user_id, "lab_exam.started", f"exam={exam_id}")
                conn.commit()
            remaining = expires_at - now
            if remaining <= 0:
                raise ValueError("The exam time has expired.")
            return remaining
        finally:
            conn.close()

    def submit_exam(self, exam_id: int, user_id: int, solution_code: str) -> bool:
        if not solution_code.strip():
            raise ValueError("Exam submission cannot be empty.")
        conn = get_connection()
        try:
            student = conn.execute("SELECT st.id FROM students st JOIN users u ON u.id = st.user_id WHERE st.user_id = ? AND u.role = 'student'", (user_id,)).fetchone()
            if not student:
                raise PermissionError("A student account is required to submit an exam.")
            student_id = student[0]
            cursor = conn.execute("""UPDATE lab_exam_submissions SET solution_code = ?, submitted_at = CURRENT_TIMESTAMP
                WHERE exam_id = ? AND student_id = ? AND submitted_at IS NULL AND expires_at > ?
                AND EXISTS (SELECT 1 FROM lab_exams WHERE id = ? AND is_active = 1)""",
                (solution_code, exam_id, student_id, int(time.time()), exam_id))
            if cursor.rowcount != 1:
                raise ValueError("The exam is not started, has expired, or was already submitted.")
            _audit(conn.cursor(), user_id, "lab_exam.submitted", f"exam={exam_id}; student={student_id}")
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


lab_exam_assistant = LabExamAssistant()
