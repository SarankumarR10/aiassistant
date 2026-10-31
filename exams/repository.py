"""Faculty-authorized authoring and publishing for structured online exams."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from database.database import _audit, get_connection


EXAM_TYPES = (
    "MCQ", "Multiple Select", "True/False", "Fill in the Blank",
    "Short Answer", "Descriptive", "Programming", "Mixed",
)
QUESTION_TYPES = {
    "mcq", "multiple_select", "true_false", "fill_blank",
    "short_answer", "descriptive", "programming",
}
PROGRAMMING_LANGUAGES = {"python", "java", "c", "c++"}


def _faculty_exists(conn, faculty_id: int) -> bool:
    row = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
    return bool(row and row[0] == "faculty")


def _iso_utc(value: str | None, field: str) -> str | None:
    if value is None or not str(value).strip():
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be a valid ISO date and time.") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone, for example +00:00.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def create_exam(faculty_id: int, subject_id: int, title: str, *, exam_type: str = "Mixed",
                duration_minutes: int = 60, passing_marks: float = 0,
                starts_at: str | None = None, ends_at: str | None = None,
                negative_marking: bool = False, max_violations: int = 3,
                auto_submit: bool = True, randomize_questions: bool = False,
                randomize_options: bool = False, class_id: int | None = None) -> int:
    """Create a draft exam. Questions determine the final total marks at publish time."""
    title = str(title or "").strip()
    exam_type = str(exam_type or "").strip()
    try:
        duration_minutes = int(duration_minutes)
        max_violations = int(max_violations)
        passing_marks = float(passing_marks)
    except (TypeError, ValueError) as error:
        raise ValueError("Duration, passing marks, and violation limit must be valid numbers.") from error
    start = _iso_utc(starts_at, "Start time")
    end = _iso_utc(ends_at, "End time")
    if not title:
        raise ValueError("Enter an exam name.")
    if exam_type not in EXAM_TYPES:
        raise ValueError("Choose a supported exam type.")
    if not 1 <= duration_minutes <= 1440:
        raise ValueError("Exam duration must be between 1 minute and 24 hours.")
    if not math.isfinite(passing_marks) or passing_marks < 0:
        raise ValueError("Passing marks cannot be negative.")
    if not 1 <= max_violations <= 20:
        raise ValueError("Set the violation limit between 1 and 20.")
    if (start is None) != (end is None):
        raise ValueError("Provide both a start and end time, or leave both empty for an unscheduled exam.")
    if start and end and datetime.fromisoformat(end) <= datetime.fromisoformat(start):
        raise ValueError("The exam end time must be after its start time.")

    conn = get_connection()
    try:
        if not _faculty_exists(conn, faculty_id):
            raise PermissionError("Only faculty can create an exam.")
        if not conn.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
            raise ValueError("Choose a valid course.")
        if class_id is not None and not conn.execute("""SELECT 1 FROM teaching_assignments
            WHERE class_id = ? AND subject_id = ? AND faculty_id = ?""",
            (class_id, subject_id, faculty_id)).fetchone():
            raise PermissionError("This subject is not assigned to you for the selected class.")
        cursor = conn.execute("""INSERT INTO online_exams
            (faculty_id, subject_id, title, exam_type, duration_minutes, starts_at, ends_at,
             passing_marks, negative_marking, max_violations, auto_submit,
             randomize_questions, randomize_options, status, class_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)""",
            (faculty_id, subject_id, title, exam_type, duration_minutes, start, end,
             passing_marks, int(bool(negative_marking)), max_violations,
             int(bool(auto_submit)), int(bool(randomize_questions)), int(bool(randomize_options)), class_id))
        exam_id = cursor.lastrowid
        _audit(conn.cursor(), faculty_id, "online_exam.created", f"exam={exam_id}; title={title}")
        conn.commit()
        return exam_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _normalize_options(question_type: str, options: Any, correct: Any) -> tuple[list[dict], Any]:
    if question_type == "true_false" and not options:
        options = ["True", "False"]
        correct_text = str(correct).strip().casefold()
        if correct_text not in {"true", "false"}:
            raise ValueError("Choose True or False as the correct answer.")
        options = [{"text": text, "is_correct": text.casefold() == correct_text} for text in options]
    if not isinstance(options, (list, tuple)) or len(options) < 2:
        raise ValueError("Add at least two answer options.")
    normalized = []
    for index, option in enumerate(options, start=1):
        if isinstance(option, dict):
            text = str(option.get("text", "")).strip()
            is_correct = bool(option.get("is_correct", False))
        else:
            text = str(option).strip()
            is_correct = False
        if not text:
            raise ValueError("Answer options cannot be empty.")
        normalized.append({"order": index, "text": text, "is_correct": is_correct})
    if len({item["text"].casefold() for item in normalized}) != len(normalized):
        raise ValueError("Answer options must be unique.")

    if correct is not None and question_type in {"mcq", "multiple_select"}:
        supplied = correct if isinstance(correct, (list, tuple, set)) else [correct]
        chosen = set()
        for value in supplied:
            match = next((item for item in normalized if (
                str(item["order"]) == str(value).strip()
                or item["text"].casefold() == str(value).strip().casefold()
            )), None)
            if not match:
                raise ValueError("The correct answer must refer to one of the listed options.")
            chosen.add(match["order"])
        for item in normalized:
            item["is_correct"] = item["order"] in chosen
    correct_orders = [item["order"] for item in normalized if item["is_correct"]]
    if question_type == "mcq" and len(correct_orders) != 1:
        raise ValueError("Choose exactly one correct option for an MCQ.")
    if question_type == "multiple_select" and not correct_orders:
        raise ValueError("Choose at least one correct option for a multiple-select question.")
    if question_type == "true_false" and len(correct_orders) != 1:
        raise ValueError("Choose exactly one correct True/False option.")
    if question_type == "mcq":
        key = correct_orders[0]
    elif question_type == "multiple_select":
        key = correct_orders
    elif question_type == "true_false":
        key = normalized[correct_orders[0] - 1]["text"].casefold() == "true"
    else:
        key = None
    return normalized, key


def create_question(faculty_id: int, subject_id: int, data: dict[str, Any]) -> int:
    """Create a reusable question-bank entry and its options or coding cases."""
    if not isinstance(data, dict):
        raise ValueError("Question data must be provided as a structured object.")
    kind = str(data.get("question_type", "")).strip().casefold().replace(" ", "_")
    kind = {"multiple_choice": "mcq", "true/false": "true_false", "fill_in_the_blank": "fill_blank", "coding": "programming"}.get(kind, kind)
    if kind not in QUESTION_TYPES:
        raise ValueError("Choose a supported question type.")
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("Enter the question text.")
    try:
        marks = float(data.get("marks", 1))
        negative = float(data.get("negative_marks", 0))
        time_limit = int(data.get("time_limit_seconds", 5))
        memory_limit = int(data.get("memory_limit_mb", 256))
    except (TypeError, ValueError) as error:
        raise ValueError("Question marks and resource limits must be valid numbers.") from error
    if (not math.isfinite(marks) or not math.isfinite(negative)
            or marks <= 0 or negative < 0 or negative > marks):
        raise ValueError("Question marks must be positive and negative marks cannot exceed them.")
    difficulty = str(data.get("difficulty", "Medium"))
    if difficulty not in {"Easy", "Medium", "Hard"}:
        raise ValueError("Difficulty must be Easy, Medium, or Hard.")
    matching_mode = str(data.get("matching_mode", "case_insensitive"))
    if matching_mode not in {"exact", "case_insensitive", "whitespace_insensitive"}:
        raise ValueError("Choose a supported answer matching rule.")
    if not 1 <= time_limit <= 60 or not 32 <= memory_limit <= 1024:
        raise ValueError("Code limits must be 1–60 seconds and 32–1024 MB.")

    options, key = [], data.get("correct_answer")
    auto_grade = bool(data.get("auto_grade", False))
    accepted = data.get("accepted_answers")
    if kind in {"mcq", "multiple_select", "true_false"}:
        options, key = _normalize_options(kind, data.get("options"), key)
    elif kind == "fill_blank" or (kind == "short_answer" and auto_grade):
        accepted = accepted if accepted is not None else key
        if isinstance(accepted, str):
            accepted = [accepted]
        if not isinstance(accepted, (list, tuple)) or not accepted or any(not str(item).strip() for item in accepted):
            raise ValueError("Provide one or more accepted answers for automatic text grading.")
        key = accepted[0]
    elif kind in {"short_answer", "descriptive"}:
        auto_grade = False
        accepted = None
        key = None

    language = str(data.get("programming_language", "")).strip().casefold()
    test_cases = data.get("test_cases", []) or []
    if kind == "programming":
        if language not in PROGRAMMING_LANGUAGES:
            raise ValueError("Choose Java, Python, C, or C++ for a programming question.")
        if not isinstance(test_cases, (list, tuple)) or not test_cases:
            raise ValueError("Add at least one programming test case.")
        if not any(bool(case.get("is_hidden", True)) for case in test_cases if isinstance(case, dict)):
            raise ValueError("Add at least one hidden test case for automatic code evaluation.")
        for case in test_cases:
            if not isinstance(case, dict) or "expected_output" not in case:
                raise ValueError("Every test case needs an expected output.")
            try:
                case_marks = float(case.get("marks", 0))
            except (TypeError, ValueError) as error:
                raise ValueError("Test-case marks must be valid numbers.") from error
            if not math.isfinite(case_marks) or case_marks < 0:
                raise ValueError("Test-case marks cannot be negative.")
    else:
        language = ""
        test_cases = []

    conn = get_connection()
    try:
        if not _faculty_exists(conn, faculty_id):
            raise PermissionError("Only faculty can add questions to the question bank.")
        if not conn.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
            raise ValueError("Choose a valid course.")
        cursor = conn.execute("""INSERT INTO online_questions
            (faculty_id, subject_id, question_type, prompt, topic, difficulty, marks,
             negative_marks, correct_answer, accepted_answers, matching_mode, auto_grade,
             explanation, programming_language, starter_code, input_format, output_format,
             constraints_text, sample_cases, time_limit_seconds, memory_limit_mb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (faculty_id, subject_id, kind, prompt, str(data.get("topic", "")).strip(),
             difficulty, marks, negative,
             json.dumps(key, ensure_ascii=False) if key is not None else None,
             json.dumps(accepted, ensure_ascii=False) if accepted is not None else None,
             matching_mode, int(auto_grade),
             str(data.get("explanation", "")).strip(), language,
             str(data.get("starter_code", "")), str(data.get("input_format", "")),
             str(data.get("output_format", "")), str(data.get("constraints", "")),
             json.dumps([case for case in test_cases if not case.get("is_hidden", True)], ensure_ascii=False),
             time_limit, memory_limit))
        question_id = cursor.lastrowid
        for option in options:
            conn.execute("""INSERT INTO online_question_options
                (question_id, option_order, option_text, is_correct) VALUES (?, ?, ?, ?)""",
                (question_id, option["order"], option["text"], int(option["is_correct"])))
        for index, case in enumerate(test_cases, start=1):
            conn.execute("""INSERT INTO online_coding_test_cases
                (question_id, case_order, input_text, expected_output, is_hidden, marks)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (question_id, index, str(case.get("input", "")), str(case["expected_output"]),
                 int(bool(case.get("is_hidden", True))), float(case.get("marks", 0))))
        _audit(conn.cursor(), faculty_id, "online_question.created", f"question={question_id}; type={kind}")
        conn.commit()
        return question_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_question_to_exam(faculty_id: int, exam_id: int, question_id: int,
                         marks_override: float | None = None) -> int:
    conn = get_connection()
    try:
        if not _faculty_exists(conn, faculty_id):
            raise PermissionError("Only faculty can add questions to an exam.")
        exam = conn.execute("SELECT subject_id, status FROM online_exams WHERE id = ? AND faculty_id = ?",
                            (exam_id, faculty_id)).fetchone()
        question = conn.execute("SELECT subject_id, faculty_id, marks, negative_marks FROM online_questions WHERE id = ?",
                                (question_id,)).fetchone()
        if not exam or exam[1] != "draft":
            raise ValueError("Questions can only be added to an exam draft owned by this faculty account.")
        if not question or question[0] != exam[0] or question[1] != faculty_id:
            raise PermissionError("Choose a question from your own question bank for this course.")
        override = None if marks_override is None else float(marks_override)
        if override is not None and override <= 0:
            raise ValueError("Question marks must be greater than zero.")
        if override is not None and override < float(question[3]):
            raise ValueError("Exam marks cannot be lower than the question's negative-mark penalty.")
        order = conn.execute("SELECT COALESCE(MAX(question_order), 0) + 1 FROM online_exam_questions WHERE exam_id = ?",
                             (exam_id,)).fetchone()[0]
        cursor = conn.execute("""INSERT INTO online_exam_questions
            (exam_id, question_id, question_order, marks_override) VALUES (?, ?, ?, ?)""",
            (exam_id, question_id, order, override))
        _audit(conn.cursor(), faculty_id, "online_exam.question_added", f"exam={exam_id}; question={question_id}")
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_question_from_exam(faculty_id: int, exam_id: int, question_id: int) -> None:
    """Remove a question from an owned draft without deleting it from the question bank."""
    conn = get_connection()
    try:
        if not _faculty_exists(conn, faculty_id):
            raise PermissionError("Only faculty can remove exam questions.")
        exam = conn.execute("SELECT status FROM online_exams WHERE id = ? AND faculty_id = ?",
                            (exam_id, faculty_id)).fetchone()
        if not exam or exam[0] != "draft":
            raise ValueError("Questions can only be removed from your own draft exam.")
        cursor = conn.execute(
            "DELETE FROM online_exam_questions WHERE exam_id = ? AND question_id = ?",
            (exam_id, question_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("That question is not attached to this exam.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def publish_exam(faculty_id: int, exam_id: int) -> float:
    """Publish a validated draft and set its authoritative total marks."""
    conn = get_connection()
    try:
        if not _faculty_exists(conn, faculty_id):
            raise PermissionError("Only faculty can publish an exam.")
        exam = conn.execute("SELECT passing_marks, status, exam_type FROM online_exams WHERE id = ? AND faculty_id = ?",
                            (exam_id, faculty_id)).fetchone()
        if not exam or exam[1] != "draft":
            raise ValueError("Only your own exam draft can be published.")
        questions = conn.execute("""SELECT q.id, q.question_type, q.marks, eq.marks_override
            FROM online_exam_questions eq JOIN online_questions q ON q.id = eq.question_id
            WHERE eq.exam_id = ? ORDER BY eq.question_order""", (exam_id,)).fetchall()
        if not questions:
            raise ValueError("Add at least one question before publishing.")
        allowed_types = {
            "MCQ": {"mcq"}, "Multiple Select": {"multiple_select"},
            "True/False": {"true_false"}, "Fill in the Blank": {"fill_blank"},
            "Short Answer": {"short_answer"}, "Descriptive": {"descriptive"},
            "Programming": {"programming"}, "Mixed": QUESTION_TYPES,
        }
        if any(row[1] not in allowed_types[exam[2]] for row in questions):
            raise ValueError(f"This {exam[2]} exam contains a question of a different type.")
        total = 0.0
        for question_id, question_type, marks, override in questions:
            total += float(override if override is not None else marks)
            if question_type == "programming":
                hidden = conn.execute("""SELECT COUNT(*) FROM online_coding_test_cases
                    WHERE question_id = ? AND is_hidden = 1""", (question_id,)).fetchone()[0]
                if hidden < 1:
                    raise ValueError("Every coding question needs at least one hidden test case.")
        passing = float(exam[0] or 0)
        if total <= 0 or passing > total:
            raise ValueError("Passing marks must be between zero and the exam total.")
        conn.execute("""UPDATE online_exams SET total_marks = ?, status = 'published',
            updated_at = CURRENT_TIMESTAMP WHERE id = ? AND faculty_id = ? AND status = 'draft'""",
            (total, exam_id, faculty_id))
        _audit(conn.cursor(), faculty_id, "online_exam.published", f"exam={exam_id}; total={total:g}")
        conn.commit()
        return total
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_online_exam_catalog(faculty_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        if not _faculty_exists(conn, faculty_id):
            raise PermissionError("Only faculty can view online exams.")
        return conn.execute("""SELECT e.id, s.code, e.title, e.exam_type, e.duration_minutes,
            e.status, e.total_marks, e.starts_at, e.ends_at, c.department, c.year_of_study,
            c.section, c.academic_year
            FROM online_exams e JOIN subjects s ON s.id = e.subject_id
            LEFT JOIN academic_classes c ON c.id = e.class_id
            WHERE e.faculty_id = ? AND e.status <> 'deleted'
            ORDER BY e.created_at DESC, e.id DESC""", (faculty_id,)).fetchall()
    finally:
        conn.close()


def get_exam_preview(faculty_id: int, exam_id: int) -> dict[str, Any]:
    """Return full answer keys and hidden cases only to the owning faculty member."""
    conn = get_connection()
    try:
        if not _faculty_exists(conn, faculty_id):
            raise PermissionError("Only faculty can preview an exam.")
        exam = conn.execute("SELECT * FROM online_exams WHERE id = ? AND faculty_id = ?",
                            (exam_id, faculty_id)).fetchone()
        if not exam:
            raise ValueError("Exam not found.")
        columns = (
            "id", "faculty_id", "subject_id", "title", "exam_type", "duration_minutes",
            "starts_at", "ends_at", "total_marks", "passing_marks", "negative_marking",
            "max_violations", "violation_action", "auto_submit", "randomize_questions",
            "randomize_options", "status", "created_at", "updated_at", "class_id",
        )
        questions = conn.execute("""SELECT q.*, eq.question_order, eq.marks_override
            FROM online_exam_questions eq JOIN online_questions q ON q.id = eq.question_id
            WHERE eq.exam_id = ? ORDER BY eq.question_order""", (exam_id,)).fetchall()
        question_columns = (
            "id", "faculty_id", "subject_id", "question_type", "prompt", "topic", "difficulty",
            "marks", "negative_marks", "correct_answer", "accepted_answers", "matching_mode",
            "auto_grade", "explanation", "programming_language", "starter_code", "input_format",
            "output_format", "constraints_text", "sample_cases", "time_limit_seconds",
            "memory_limit_mb", "created_at", "question_order", "marks_override",
        )
        prepared = []
        for row in questions:
            question = dict(zip(question_columns, row))
            question["options"] = conn.execute("""SELECT option_order, option_text, is_correct
                FROM online_question_options WHERE question_id = ? ORDER BY option_order""",
                (question["id"],)).fetchall()
            question["test_cases"] = conn.execute("""SELECT case_order, input_text, expected_output, is_hidden, marks
                FROM online_coding_test_cases WHERE question_id = ? ORDER BY case_order""",
                (question["id"],)).fetchall()
            prepared.append(question)
        return {"exam": dict(zip(columns, exam)), "questions": prepared}
    finally:
        conn.close()
