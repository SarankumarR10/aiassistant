"""Student exam attempts with server-clock deadlines and private autosaves."""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from typing import Any

from database.database import _audit, get_connection
from exams.evaluation import evaluate_exam


_EXAM_COLUMNS = (
    "id", "faculty_id", "subject_id", "title", "exam_type", "duration_minutes",
    "starts_at", "ends_at", "total_marks", "passing_marks", "negative_marking",
    "max_violations", "violation_action", "auto_submit", "randomize_questions",
    "randomize_options", "status", "created_at", "updated_at", "class_id",
)
_QUESTION_COLUMNS = (
    "id", "question_type", "prompt", "topic", "difficulty", "marks", "negative_marks",
    "correct_answer", "accepted_answers", "matching_mode", "auto_grade", "explanation",
    "programming_language", "starter_code", "input_format", "output_format", "constraints_text",
    "sample_cases", "time_limit_seconds", "memory_limit_mb", "question_order", "marks_override",
)


def _epoch(value: str | None) -> int | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Exam schedule values must include a timezone.")
    return int(parsed.timestamp())


def _student(conn, user_id: int):
    return conn.execute("""SELECT st.id FROM students st JOIN users u ON u.id = st.user_id
        WHERE st.user_id = ? AND u.role = 'student'""", (user_id,)).fetchone()


def get_student_exam_catalog(user_id: int) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        if not _student(conn, user_id):
            raise PermissionError("A student account is required to view exams.")
        rows = conn.execute("""SELECT e.id, s.code, s.name, e.title, e.exam_type, e.duration_minutes,
            e.starts_at, e.ends_at, e.total_marks, e.passing_marks, e.status,
            a.id, a.status, a.ends_at, a.submitted_at, r.marks_awarded, r.total_marks, r.outcome
            FROM online_exams e JOIN subjects s ON s.id = e.subject_id
            LEFT JOIN students st ON st.user_id = ?
            LEFT JOIN online_exam_attempts a ON a.exam_id = e.id AND a.student_id = st.id
            LEFT JOIN online_exam_results r ON r.attempt_id = a.id
            WHERE e.status <> 'deleted' AND (e.class_id IS NULL OR e.class_id = st.class_id)
              AND (e.status = 'published' OR a.id IS NOT NULL)
            ORDER BY CASE WHEN a.id IS NOT NULL AND a.status IN ('in_progress','paused') THEN 0
                          WHEN e.status = 'published' THEN 1 ELSE 2 END,
                     e.starts_at, e.id DESC""", (user_id,)).fetchall()
        now = int(time.time())
        exams = []
        for row in rows:
            (exam_id, code, subject, title, exam_type, duration, start, end, total, passing,
             exam_status, attempt_id, attempt_status, attempt_end, submitted_at,
             result_marks, result_total, result_outcome) = row
            start_epoch, end_epoch = _epoch(start), _epoch(end)
            if attempt_id and attempt_status in ("submitted", "auto_submitted", "ended"):
                display_status = "Completed"
            elif attempt_status == "paused":
                display_status = "Paused — faculty review required"
            elif attempt_id:
                display_status = "In progress"
            elif start_epoch and start_epoch > now:
                display_status = "Upcoming"
            elif end_epoch and end_epoch <= now:
                display_status = "Closed"
            else:
                display_status = "Available"
            exams.append({
                "id": exam_id, "subject_code": code, "subject_name": subject,
                "title": title, "exam_type": exam_type, "duration_minutes": duration,
                "starts_at": start, "ends_at": end, "total_marks": total,
                "passing_marks": passing, "status": display_status,
                "attempt_id": attempt_id, "attempt_status": attempt_status,
                "attempt_ends_at": attempt_end, "submitted_at": submitted_at,
                "result_marks": result_marks, "result_total": result_total,
                "result_outcome": result_outcome,
            })
        return exams
    finally:
        conn.close()


def start_attempt(user_id: int, exam_id: int) -> dict[str, Any]:
    """Start or resume a student's attempt; the backend clock owns the deadline."""
    now = int(time.time())
    expired_existing = False
    conn = get_connection()
    try:
        student = _student(conn, user_id)
        if not student:
            raise PermissionError("A student account is required to start an exam.")
        student_id = student[0]
        exam = conn.execute("SELECT * FROM online_exams WHERE id = ?", (exam_id,)).fetchone()
        if not exam:
            raise ValueError("This exam is no longer available.")
        exam_data = dict(zip(_EXAM_COLUMNS, exam))
        student_class = conn.execute("SELECT class_id FROM students WHERE id = ?", (student_id,)).fetchone()[0]
        if exam_data.get("class_id") is not None and int(exam_data["class_id"]) != int(student_class or 0):
            raise PermissionError("This exam is not assigned to your academic class.")
        attempt = conn.execute("""SELECT id, ends_at, status FROM online_exam_attempts
            WHERE exam_id = ? AND student_id = ?""", (exam_id, student_id)).fetchone()

        if attempt:
            attempt_id, deadline, attempt_status = attempt
            if attempt_status in ("submitted", "auto_submitted", "ended"):
                raise ValueError("You have already completed this exam.")
            if attempt_status == "paused":
                raise ValueError("This attempt is paused. Contact faculty for approval to continue.")
            if now >= int(deadline):
                expired_existing = True
            else:
                conn.commit()
                return get_attempt(user_id, int(attempt_id))
        else:
            if exam_data["status"] != "published":
                raise ValueError("This exam is not open for new attempts.")
            start_at, end_at = _epoch(exam_data["starts_at"]), _epoch(exam_data["ends_at"])
            if start_at is not None and now < start_at:
                raise ValueError("This exam has not opened yet.")
            if end_at is not None and now >= end_at:
                raise ValueError("The exam window has closed.")
            questions = conn.execute("""SELECT q.id FROM online_exam_questions eq
                JOIN online_questions q ON q.id = eq.question_id WHERE eq.exam_id = ?
                ORDER BY eq.question_order""", (exam_id,)).fetchall()
            if not questions:
                raise ValueError("This exam has no questions yet. Contact faculty.")
            question_ids = [int(row[0]) for row in questions]
            if exam_data["randomize_questions"]:
                random.SystemRandom().shuffle(question_ids)
            deadline = now + int(exam_data["duration_minutes"]) * 60
            if end_at is not None:
                deadline = min(deadline, end_at)
            if deadline <= now:
                raise ValueError("There is no time remaining in the exam window.")
            cursor = conn.execute("""INSERT INTO online_exam_attempts
                (exam_id, student_id, started_at, ends_at, status)
                VALUES (?, ?, ?, ?, 'in_progress')""", (exam_id, student_id, now, deadline))
            attempt_id = int(cursor.lastrowid)
            for position, question_id in enumerate(question_ids, start=1):
                option_rows = conn.execute("SELECT option_order FROM online_question_options WHERE question_id = ? ORDER BY option_order",
                                           (question_id,)).fetchall()
                option_order = [int(row[0]) for row in option_rows]
                if exam_data["randomize_options"]:
                    random.SystemRandom().shuffle(option_order)
                conn.execute("""INSERT INTO online_attempt_questions
                    (attempt_id, question_id, question_order, option_order_json)
                    VALUES (?, ?, ?, ?)""",
                    (attempt_id, question_id, position, json.dumps(option_order)))
            _audit(conn.cursor(), user_id, "online_exam.started", f"exam={exam_id}; attempt={attempt_id}")
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if expired_existing:
        submit_attempt(user_id, int(attempt_id), allow_expired=True)
        raise ValueError("The time expired. Your saved answers were submitted automatically.")
    return get_attempt(user_id, int(attempt_id))


def get_attempt(user_id: int, attempt_id: int) -> dict[str, Any]:
    """Return this student's attempt with answer keys and hidden cases removed."""
    conn = get_connection()
    try:
        student = _student(conn, user_id)
        if not student:
            raise PermissionError("A student account is required to view an attempt.")
        row = conn.execute("""SELECT a.id, a.exam_id, a.started_at, a.ends_at, a.status,
            a.violation_count, e.title, e.exam_type, e.total_marks
            FROM online_exam_attempts a JOIN online_exams e ON e.id = a.exam_id
            WHERE a.id = ? AND a.student_id = ?""", (attempt_id, student[0])).fetchone()
        if not row:
            raise PermissionError("This attempt does not belong to your student account.")
        attempt = dict(zip(("id", "exam_id", "started_at", "ends_at", "status",
                            "violation_count", "title", "exam_type", "total_marks"), row))
        now = int(time.time())
        attempt["seconds_remaining"] = max(0, int(attempt["ends_at"]) - now)
        order_rows = conn.execute("""SELECT aq.question_id, aq.question_order, aq.option_order_json,
            q.question_type, q.prompt, q.marks, q.topic, q.difficulty, q.programming_language,
            q.starter_code, q.input_format, q.output_format, q.constraints_text,
            q.time_limit_seconds, q.memory_limit_mb, eq.marks_override
            FROM online_attempt_questions aq
            JOIN online_questions q ON q.id = aq.question_id
            JOIN online_exam_questions eq ON eq.exam_id = ? AND eq.question_id = aq.question_id
            WHERE aq.attempt_id = ? ORDER BY aq.question_order""", (attempt["exam_id"], attempt_id)).fetchall()
        questions = []
        for row in order_rows:
            (qid, position, option_json, kind, prompt, marks, topic, difficulty, language,
             starter, input_format, output_format, constraints, time_limit, memory_limit, override) = row
            option_order = json.loads(option_json or "[]")
            options = []
            for order in option_order:
                option = conn.execute("""SELECT option_text FROM online_question_options
                    WHERE question_id = ? AND option_order = ?""", (qid, order)).fetchone()
                if option:
                    options.append({"order": order, "text": option[0]})
            sample_cases = conn.execute("""SELECT input_text, expected_output FROM online_coding_test_cases
                WHERE question_id = ? AND is_hidden = 0 ORDER BY case_order""", (qid,)).fetchall()
            saved = conn.execute("""SELECT answer_json, evaluation_status FROM online_student_answers
                WHERE attempt_id = ? AND question_id = ?""", (attempt_id, qid)).fetchone()
            questions.append({
                "id": qid, "number": position, "question_type": kind, "prompt": prompt,
                "marks": float(override if override is not None else marks), "topic": topic,
                "difficulty": difficulty, "options": options,
                "programming_language": language, "starter_code": starter,
                "input_format": input_format, "output_format": output_format,
                "constraints": constraints, "time_limit_seconds": time_limit,
                "memory_limit_mb": memory_limit,
                "sample_cases": [{"input": sample[0], "expected_output": sample[1]} for sample in sample_cases],
                "answer": json.loads(saved[0]) if saved and saved[0] else None,
                "evaluation_status": saved[1] if saved else "ungraded",
            })
        attempt["questions"] = questions
        return attempt
    finally:
        conn.close()


def save_answer(user_id: int, attempt_id: int, question_id: int, answer: Any) -> None:
    """Autosave one structured response if its owned attempt is still open."""
    try:
        answer_json = json.dumps(answer, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise ValueError("The answer could not be saved in a supported format.") from error
    if len(answer_json) > 120_000:
        raise ValueError("This answer is too large to save.")
    conn = get_connection()
    try:
        student = _student(conn, user_id)
        if not student:
            raise PermissionError("A student account is required to save exam answers.")
        attempt = conn.execute("""SELECT status, ends_at FROM online_exam_attempts
            WHERE id = ? AND student_id = ?""", (attempt_id, student[0])).fetchone()
        if not attempt:
            raise PermissionError("This attempt does not belong to your student account.")
        if attempt[0] != "in_progress":
            raise ValueError("This exam attempt is not accepting answers.")
        if int(time.time()) >= int(attempt[1]):
            raise ValueError("The exam time has expired. Submit the saved answers now.")
        if not conn.execute("SELECT 1 FROM online_attempt_questions WHERE attempt_id = ? AND question_id = ?",
                            (attempt_id, question_id)).fetchone():
            raise PermissionError("This question is not part of your exam attempt.")
        conn.execute("""INSERT INTO online_student_answers(attempt_id, question_id, answer_json, saved_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(attempt_id, question_id) DO UPDATE SET
              answer_json = excluded.answer_json, saved_at = CURRENT_TIMESTAMP""",
            (attempt_id, question_id, answer_json))
        conn.execute("UPDATE online_exam_attempts SET last_saved_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (attempt_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def submit_attempt(user_id: int, attempt_id: int, *, allow_expired: bool = False) -> dict[str, Any]:
    """Finalize an attempt and store objective scores; coding/descriptive remain pending review."""
    conn = get_connection()
    try:
        student = _student(conn, user_id)
        if not student:
            raise PermissionError("A student account is required to submit an exam.")
        row = conn.execute("""SELECT a.exam_id, a.ends_at, a.status, e.passing_marks, e.negative_marking
            FROM online_exam_attempts a JOIN online_exams e ON e.id = a.exam_id
            WHERE a.id = ? AND a.student_id = ?""", (attempt_id, student[0])).fetchone()
        if not row:
            raise PermissionError("This attempt does not belong to your student account.")
        exam_id, deadline, status, passing, negative = row
        if status != "in_progress":
            raise ValueError("This exam attempt has already been submitted or paused.")
        expired = int(time.time()) >= int(deadline)
        if expired and not allow_expired:
            raise ValueError("The exam time has expired; automatic submission is required.")
        if not expired and allow_expired:
            raise ValueError("The exam deadline has not been reached.")

        question_rows = conn.execute("""SELECT q.id, q.question_type, q.marks, q.negative_marks,
            q.correct_answer, q.accepted_answers, q.matching_mode, q.auto_grade, eq.marks_override
            FROM online_attempt_questions aq JOIN online_questions q ON q.id = aq.question_id
            JOIN online_exam_questions eq ON eq.exam_id = ? AND eq.question_id = aq.question_id
            WHERE aq.attempt_id = ? ORDER BY aq.question_order""", (exam_id, attempt_id)).fetchall()
        answer_rows = conn.execute("SELECT question_id, answer_json FROM online_student_answers WHERE attempt_id = ?",
                                   (attempt_id,)).fetchall()
        answers = {question_id: json.loads(value) if value else None for question_id, value in answer_rows}
        questions = [{
            "id": qid, "question_type": kind, "marks": override if override is not None else marks,
            "negative_marks": penalty, "correct_answer": correct, "accepted_answers": accepted,
            "matching_mode": matching, "auto_grade": bool(auto_grade),
        } for qid, kind, marks, penalty, correct, accepted, matching, auto_grade, override in question_rows]
        result = evaluate_exam(questions, answers, float(passing), negative_marking=bool(negative))
        for evaluation in result["results"]:
            conn.execute("""INSERT INTO online_student_answers
                (attempt_id, question_id, answer_json, marks_awarded, evaluation_status, feedback)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(attempt_id, question_id) DO UPDATE SET
                  marks_awarded = excluded.marks_awarded,
                  evaluation_status = excluded.evaluation_status,
                  feedback = excluded.feedback""",
                (attempt_id, evaluation["question_id"],
                 json.dumps(answers.get(evaluation["question_id"]), ensure_ascii=False)
                 if evaluation["question_id"] in answers else None,
                 evaluation["marks_awarded"], evaluation["status"], evaluation["feedback"]))
        outcome = result["outcome"]
        conn.execute("""INSERT INTO online_exam_results
            (attempt_id, marks_awarded, total_marks, percentage, outcome, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(attempt_id) DO UPDATE SET marks_awarded = excluded.marks_awarded,
              total_marks = excluded.total_marks, percentage = excluded.percentage,
              outcome = excluded.outcome, result_json = excluded.result_json,
              evaluated_at = CURRENT_TIMESTAMP""",
            (attempt_id, result["marks_awarded"], result["total_marks"], result["percentage"],
             outcome, json.dumps(result, ensure_ascii=False)))
        final_status = "auto_submitted" if expired else "submitted"
        conn.execute("UPDATE online_exam_attempts SET status = ?, submitted_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (final_status, attempt_id))
        _audit(conn.cursor(), user_id, f"online_exam.{final_status}", f"exam={exam_id}; attempt={attempt_id}")
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
