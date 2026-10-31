import unittest

from exams.evaluation import evaluate_answer, evaluate_exam, score_programming_results


class ExamEvaluationTests(unittest.TestCase):
    def test_mcq_and_negative_marking(self):
        question = {"type": "MCQ", "marks": 2, "negative_marks": 0.5, "correct_answer": "B"}
        self.assertEqual(evaluate_answer(question, "B")["marks_awarded"], 2)
        self.assertEqual(evaluate_answer(question, "A")["marks_awarded"], -0.5)

    def test_multiple_select_compares_sets(self):
        question = {"type": "multiple_select", "marks": 3, "correct_answer": ["A", "C"]}
        self.assertTrue(evaluate_answer(question, ["C", "A"])["correct"])
        self.assertFalse(evaluate_answer(question, ["A"])["correct"])

    def test_true_false_accepts_boolean_text(self):
        question = {"type": "true_false", "marks": 1, "correct_answer": True}
        self.assertTrue(evaluate_answer(question, "true")["correct"])
        self.assertFalse(evaluate_answer(question, "false")["correct"])

    def test_fill_blank_matching_modes(self):
        question = {"type": "fill_blank", "marks": 1, "accepted_answers": ["binary tree"]}
        self.assertTrue(evaluate_answer(question, "BINARY TREE")["correct"])
        question["matching_mode"] = "whitespace_insensitive"
        self.assertTrue(evaluate_answer(question, "binary   tree")["correct"])

    def test_descriptive_is_pending_faculty_review(self):
        result = evaluate_answer({"type": "descriptive", "marks": 5}, "essay")
        self.assertEqual(result["status"], "pending_review")
        self.assertIsNone(result["marks_awarded"])

    def test_programming_is_scored_from_sandbox_results(self):
        result = score_programming_results(
            {"type": "programming", "marks": 10},
            [{"passed": True}, {"passed": True}, {"passed": False}, {"passed": True}],
        )
        self.assertEqual(result["marks_awarded"], 7.5)
        self.assertEqual((result["passed_cases"], result["total_cases"]), (3, 4))

    def test_exam_holds_pass_fail_until_manual_review(self):
        questions = [
            {"id": 1, "type": "mcq", "marks": 2, "correct_answer": "A"},
            {"id": 2, "type": "descriptive", "marks": 3},
        ]
        result = evaluate_exam(questions, {1: "A", 2: "answer"}, passing_marks=3)
        self.assertEqual(result["status"], "pending_evaluation")
        self.assertEqual(result["marks_awarded"], 2)
        self.assertEqual(result["outcome"], "Pending review")


if __name__ == "__main__":
    unittest.main()
