"""Faculty-authorized review and manual grading for online exam submissions."""
from __future__ import annotations

import json

from database.database import _audit, get_connection


def get_submitted_exams(faculty_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can review online exams.")
        return conn.execute("""SELECT e.id, e.title, s.code, e.status
            FROM online_exams e JOIN subjects s ON s.id = e.subject_id
            WHERE e.faculty_id = ? AND e.status <> 'deleted'
            ORDER BY e.created_at DESC, e.id DESC""", (faculty_id,)).fetchall()
    finally:
        conn.close()


def get_exam_attempts(faculty_id: int, exam_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can review online exams.")
        if not conn.execute("SELECT 1 FROM online_exams WHERE id = ? AND faculty_id = ?",
                            (exam_id, faculty_id)).fetchone():
            raise PermissionError("This exam does not belong to your faculty account.")
        return conn.execute("""SELECT a.id, st.roll_number, st.name, a.submitted_at, a.status,
                COALESCE(r.marks_awarded, 0), COALESCE(r.total_marks, e.total_marks), r.outcome
            FROM online_exam_attempts a
            JOIN students st ON st.id = a.student_id
            JOIN online_exams e ON e.id = a.exam_id
            LEFT JOIN online_exam_results r ON r.attempt_id = a.id
            WHERE a.exam_id = ? AND a.status IN ('submitted','auto_submitted','ended')
            ORDER BY a.submitted_at DESC, a.id DESC""", (exam_id,)).fetchall()
    finally:
        conn.close()


def get_attempt_answers(faculty_id: int, attempt_id: int) -> dict:
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can review online exams.")
        attempt = conn.execute("""SELECT a.id, e.title, st.roll_number, st.name, e.passing_marks
            FROM online_exam_attempts a JOIN online_exams e ON e.id = a.exam_id
            JOIN students st ON st.id = a.student_id
            WHERE a.id = ? AND e.faculty_id = ?""", (attempt_id, faculty_id)).fetchone()
        if not attempt:
            raise PermissionError("This submission does not belong to your faculty account.")
        rows = conn.execute("""SELECT q.id, q.question_type, q.prompt, q.correct_answer,
                a.answer_json, a.marks_awarded, COALESCE(eq.marks_override, q.marks),
                a.evaluation_status, a.feedback
            FROM online_attempt_questions aq
            JOIN online_questions q ON q.id = aq.question_id
            JOIN online_exam_questions eq ON eq.exam_id = ? AND eq.question_id = q.id
            LEFT JOIN online_student_answers a ON a.attempt_id = aq.attempt_id AND a.question_id = q.id
            WHERE aq.attempt_id = ? ORDER BY aq.question_order""",
            (conn.execute("SELECT exam_id FROM online_exam_attempts WHERE id = ?", (attempt_id,)).fetchone()[0], attempt_id)).fetchall()
        questions = []
        for row in rows:
            qid, kind, prompt, correct, answer, marks, maximum, status, feedback = row
            try:
                answer = json.loads(answer) if answer is not None else None
            except (TypeError, json.JSONDecodeError):
                pass
            try:
                correct = json.loads(correct) if correct is not None else None
            except (TypeError, json.JSONDecodeError):
                pass
            questions.append({
                "id": qid, "type": kind, "prompt": prompt, "answer": answer,
                "correct_answer": correct, "marks_awarded": marks,
                "max_marks": maximum, "status": status or "ungraded", "feedback": feedback or "",
            })
        return {"attempt": {"id": attempt[0], "exam": attempt[1], "roll_number": attempt[2],
                             "student": attempt[3], "passing_marks": attempt[4]}, "questions": questions}
    finally:
        conn.close()


def grade_exam_answer(faculty_id: int, attempt_id: int, question_id: int,
                      marks_awarded: float, feedback: str = "") -> dict:
    """Save one manual score and refresh the attempt's aggregate result."""
    try:
        marks_awarded = float(marks_awarded)
    except (TypeError, ValueError) as error:
        raise ValueError("Enter a valid mark.") from error
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can grade online exam answers.")
        row = conn.execute("""SELECT e.id, e.passing_marks, COALESCE(eq.marks_override, q.marks),
                q.question_type, a.status
            FROM online_exam_attempts a JOIN online_exams e ON e.id = a.exam_id
            JOIN online_exam_questions eq ON eq.exam_id = e.id AND eq.question_id = ?
            JOIN online_questions q ON q.id = eq.question_id
            WHERE a.id = ? AND e.faculty_id = ?""", (question_id, attempt_id, faculty_id)).fetchone()
        if not row:
            raise PermissionError("This answer does not belong to your exam.")
        exam_id, passing, maximum, kind, attempt_status = row
        if attempt_status not in ("submitted", "auto_submitted", "ended"):
            raise ValueError("Only submitted exam answers can be graded.")
        if kind not in {"short_answer", "descriptive", "programming"}:
            raise ValueError("This question is graded automatically and cannot be manually changed here.")
        if marks_awarded < 0 or marks_awarded > float(maximum):
            raise ValueError(f"Marks must be between 0 and {float(maximum):g}.")
        conn.execute("""INSERT INTO online_student_answers
            (attempt_id, question_id, marks_awarded, evaluation_status, feedback)
            VALUES (?, ?, ?, 'graded', ?)
            ON CONFLICT(attempt_id, question_id) DO UPDATE SET
                marks_awarded = excluded.marks_awarded,
                evaluation_status = 'graded', feedback = excluded.feedback""",
            (attempt_id, question_id, marks_awarded, str(feedback or "").strip()))
        aggregates = conn.execute("""SELECT COALESCE(SUM(COALESCE(sa.marks_awarded, 0)), 0),
                COALESCE(SUM(COALESCE(eq.marks_override, q.marks)), 0),
                SUM(CASE WHEN sa.evaluation_status IN ('pending_review','pending_evaluation','ungraded')
                          OR sa.evaluation_status IS NULL THEN 1 ELSE 0 END)
            FROM online_attempt_questions aq
            JOIN online_questions q ON q.id = aq.question_id
            JOIN online_exam_questions eq ON eq.exam_id = ? AND eq.question_id = q.id
            LEFT JOIN online_student_answers sa ON sa.attempt_id = aq.attempt_id AND sa.question_id = q.id
            WHERE aq.attempt_id = ?""", (exam_id, attempt_id)).fetchone()
        marks, total, pending = float(aggregates[0]), float(aggregates[1]), int(aggregates[2] or 0)
        outcome = "Pending review" if pending else ("Pass" if marks >= float(passing) else "Fail")
        percentage = round(marks / total * 100, 2) if total else 0.0
        conn.execute("""INSERT INTO online_exam_results
            (attempt_id, marks_awarded, total_marks, percentage, outcome)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(attempt_id) DO UPDATE SET marks_awarded = excluded.marks_awarded,
              total_marks = excluded.total_marks, percentage = excluded.percentage,
              outcome = excluded.outcome, evaluated_at = CURRENT_TIMESTAMP""",
            (attempt_id, marks, total, percentage, outcome))
        _audit(conn.cursor(), faculty_id, "online_exam.answer_graded",
               f"attempt={attempt_id}; question={question_id}; marks={marks_awarded:g}")
        conn.commit()
        return {"marks_awarded": marks, "total_marks": total, "percentage": percentage, "outcome": outcome}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
