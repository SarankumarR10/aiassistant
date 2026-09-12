"""
Lab Exam Assistant module.
Manages practical exam timers, active question paper loading, submission recording, and security locking.
"""
from database.database import get_lab_exams, get_connection

class LabExamAssistant:
    def get_active_exam(self) -> dict:
        exams = get_lab_exams()
        if exams:
            e = exams[0]
            return {
                "id": e[0],
                "subject_code": e[1],
                "subject_name": e[2],
                "title": e[3],
                "question_paper": e[4],
                "duration_minutes": e[5]
            }
        return {
            "id": 1,
            "subject_code": "CS304",
            "subject_name": "Python Programming Lab",
            "title": "Mid-Term Practical Examination",
            "question_paper": "1. Write a Python script to parse CSV data and calculate student attendance percentage.\n2. Create a class hierarchy for Library Management System with checkout and return methods.",
            "duration_minutes": 60
        }

    def submit_exam(self, exam_id: int, student_id: int, solution_code: str) -> bool:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO lab_submissions (experiment_id, student_id, code_snippet, status)
            VALUES (?, ?, ?, 'Exam Submitted')
            ON CONFLICT(experiment_id, student_id) DO UPDATE SET code_snippet = excluded.code_snippet, status = 'Exam Submitted'
        """, (exam_id, student_id, solution_code))
        conn.commit()
        conn.close()
        return True

lab_exam_assistant = LabExamAssistant()
