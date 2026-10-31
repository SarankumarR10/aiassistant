"""Server-side scoring rules for objective, descriptive, and coding questions.

This module evaluates structured question/answer data only. It never executes
student code. Programming outcomes must come from the trusted sandbox service.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


_ALIASES = {
    "mcq": "mcq",
    "multiple_choice": "mcq",
    "multiple-select": "multiple_select",
    "multiple select": "multiple_select",
    "multiple_select": "multiple_select",
    "true_false": "true_false",
    "true/false": "true_false",
    "fill_blank": "fill_blank",
    "fill_in_the_blank": "fill_blank",
    "fill in the blank": "fill_blank",
    "short_answer": "short_answer",
    "descriptive": "descriptive",
    "subjective": "descriptive",
    "programming": "programming",
    "coding": "programming",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value
    return value


def _points(value: Any, field: str) -> float:
    try:
        points = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a number.") from error
    if not math.isfinite(points) or points < 0:
        raise ValueError(f"{field} must be a finite, non-negative number.")
    return points


def _question_type(question: Mapping[str, Any]) -> str:
    raw = str(question.get("question_type", question.get("type", ""))).strip().casefold()
    result = _ALIASES.get(raw)
    if result is None:
        raise ValueError(f"Unsupported question type: {raw or '(empty)'}.")
    return result


def _canonical(value: Any, mode: str = "exact") -> str:
    text = str(value)
    if mode == "case_insensitive":
        return text.casefold()
    if mode == "whitespace_insensitive":
        return re.sub(r"\s+", "", text).casefold()
    if mode != "exact":
        raise ValueError("Fill-in matching mode must be exact, case_insensitive, or whitespace_insensitive.")
    return text


def evaluate_answer(question: Mapping[str, Any], answer: Any, *, negative_marking: bool = True) -> dict[str, Any]:
    """Evaluate one answer; return score and review status without mutating input."""
    kind = _question_type(question)
    maximum = _points(question.get("marks", question.get("max_marks", 0)), "Question marks")
    penalty = _points(question.get("negative_marks", 0), "Negative marks")
    if not negative_marking:
        penalty = 0
    if penalty > maximum:
        raise ValueError("Negative marks cannot exceed the question's maximum marks.")
    expected = _json_value(question.get("correct_answer"))
    response = _json_value(answer)

    correct: bool | None
    feedback: str
    if kind == "mcq":
        if response is None or str(response).strip() == "":
            return {"status": "auto_graded", "correct": False, "marks_awarded": 0.0,
                    "max_marks": maximum, "feedback": "No answer submitted."}
        correct = response is not None and str(response).strip() == str(expected).strip()
        feedback = "Correct answer." if correct else "Incorrect answer."
    elif kind == "multiple_select":
        if not isinstance(expected, (list, tuple, set)):
            raise ValueError("Multiple-select questions need a list of correct options.")
        if response is None:
            return {"status": "auto_graded", "correct": False, "marks_awarded": 0.0,
                    "max_marks": maximum, "feedback": "No answer submitted."}
        if not isinstance(response, (list, tuple, set)):
            response = [] if response is None else [response]
        correct = {str(item).strip() for item in response} == {str(item).strip() for item in expected}
        feedback = "Correct selection." if correct else "The selected options do not match the answer key."
    elif kind == "true_false":
        def truth_value(value: Any) -> bool | None:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)) and value in (0, 1):
                return bool(value)
            token = str(value).strip().casefold()
            if token in {"true", "t", "yes", "1"}:
                return True
            if token in {"false", "f", "no", "0"}:
                return False
            return None

        expected_bool, response_bool = truth_value(expected), truth_value(response)
        if expected_bool is None:
            raise ValueError("True/False questions need a true or false answer key.")
        if response_bool is None:
            return {"status": "auto_graded", "correct": False, "marks_awarded": 0.0,
                    "max_marks": maximum, "feedback": "No answer submitted."}
        correct = response_bool is not None and response_bool == expected_bool
        feedback = "Correct answer." if correct else "Incorrect answer."
    elif kind == "fill_blank" or (kind == "short_answer" and question.get("auto_grade")):
        accepted = _json_value(question.get("accepted_answers"))
        if accepted is None:
            accepted = expected
        if isinstance(accepted, str):
            accepted = [accepted]
        if not isinstance(accepted, (list, tuple, set)) or not accepted:
            raise ValueError("Automatically graded text questions need at least one accepted answer.")
        mode = str(question.get("matching_mode", "case_insensitive" if kind == "fill_blank" else "exact"))
        if response is None or str(response).strip() == "":
            return {"status": "auto_graded", "correct": False, "marks_awarded": 0.0,
                    "max_marks": maximum, "feedback": "No answer submitted."}
        correct = response is not None and any(
            _canonical(response, mode) == _canonical(candidate, mode) for candidate in accepted
        )
        feedback = "Correct answer." if correct else "The answer does not match an accepted response."
    elif kind in {"descriptive", "short_answer"}:
        return {
            "status": "pending_review", "correct": None, "marks_awarded": None,
            "max_marks": maximum, "feedback": "Faculty evaluation required.",
        }
    elif kind == "programming":
        return {
            "status": "pending_evaluation", "correct": None, "marks_awarded": None,
            "max_marks": maximum, "feedback": "Run hidden tests in the isolated code sandbox before scoring.",
        }
    else:
        # _question_type prevents this branch; keep a defensive error if the map changes.
        raise ValueError(f"Automatic grading is not configured for question type {kind}.")

    awarded = maximum if correct else -penalty
    return {
        "status": "auto_graded", "correct": correct, "marks_awarded": awarded,
        "max_marks": maximum, "feedback": feedback,
    }


def score_programming_results(question: Mapping[str, Any], case_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Score outcomes returned by a trusted sandbox, never raw client assertions."""
    if _question_type(question) != "programming":
        raise ValueError("Sandbox outcomes can only score programming questions.")
    maximum = _points(question.get("marks", question.get("max_marks", 0)), "Question marks")
    if not case_results:
        raise ValueError("The sandbox must return at least one test-case result.")
    passed = sum(1 for result in case_results if result.get("passed") is True)
    total = len(case_results)
    awarded = maximum * passed / total
    return {
        "status": "auto_graded", "correct": passed == total,
        "marks_awarded": round(awarded, 2), "max_marks": maximum,
        "passed_cases": passed, "total_cases": total,
        "feedback": f"Passed {passed} of {total} hidden test cases.",
    }


def evaluate_exam(questions: Sequence[Mapping[str, Any]], answers: Mapping[Any, Any],
                  passing_marks: float, *, negative_marking: bool = False) -> dict[str, Any]:
    """Score an exam; withhold pass/fail until every manual/sandbox evaluation is done."""
    if not questions:
        raise ValueError("An exam must contain at least one question.")
    passing = _points(passing_marks, "Passing marks")
    results = []
    for index, question in enumerate(questions):
        question_id = question.get("id", index + 1)
        answer = answers.get(question_id, answers.get(str(question_id)))
        result = evaluate_answer(question, answer, negative_marking=negative_marking)
        result["question_id"] = question_id
        results.append(result)

    maximum = sum(result["max_marks"] for result in results)
    scored = sum(result["marks_awarded"] or 0 for result in results)
    pending = any(result["marks_awarded"] is None for result in results)
    return {
        "status": "pending_evaluation" if pending else "evaluated",
        "results": results,
        "total_marks": round(maximum, 2),
        "marks_awarded": round(scored, 2),
        "percentage": round(scored / maximum * 100, 2) if maximum else 0.0,
        "passing_marks": passing,
        "outcome": "Pending review" if pending else ("Pass" if scored >= passing else "Fail"),
    }
