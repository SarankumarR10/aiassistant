"""Faculty view for online exam submissions and marks."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView,
)

from exams.review import get_attempt_answers, get_exam_attempts, get_submitted_exams, grade_exam_answer
from gui.theme import create_section_header, style_action_button


def _display(value) -> str:
    if value is None:
        return "No answer submitted"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


class OnlineExamReviewWidget(QWidget):
    def __init__(self, faculty_id: int):
        super().__init__()
        self.faculty_id = faculty_id
        self._questions = []
        self._selected_attempt = None
        self._build_ui()
        self.refresh_exams()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        root.addWidget(create_section_header(
            "Submitted Answers and Marks", "Review student responses, check automatic scores, and grade written answers"
        ))
        row = QHBoxLayout()
        self.exam_picker = QComboBox()
        self.exam_picker.currentIndexChanged.connect(self.refresh_attempts)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_exams)
        row.addWidget(QLabel("Exam"))
        row.addWidget(self.exam_picker, 1)
        row.addWidget(refresh)
        root.addLayout(row)

        attempts_group = QGroupBox("Submitted attempts")
        attempts_layout = QVBoxLayout(attempts_group)
        self.attempts_table = QTableWidget(0, 6)
        self.attempts_table.setHorizontalHeaderLabels(["Roll No.", "Student", "Submitted", "Marks", "Outcome", "Attempt"])
        self.attempts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.attempts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.attempts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.attempts_table.itemSelectionChanged.connect(self.load_selected_attempt)
        attempts_layout.addWidget(self.attempts_table)
        root.addWidget(attempts_group)

        response_group = QGroupBox("Student answers")
        response_layout = QVBoxLayout(response_group)
        self.student_label = QLabel("Select a submitted attempt to view its answers.")
        self.student_label.setWordWrap(True)
        response_layout.addWidget(self.student_label)
        self.answers_table = QTableWidget(0, 7)
        self.answers_table.setHorizontalHeaderLabels(["#", "Type", "Question", "Student answer", "Correct answer", "Marks", "Status"])
        self.answers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.answers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.answers_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.answers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.answers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.answers_table.itemSelectionChanged.connect(self.select_question)
        response_layout.addWidget(self.answers_table)
        self.grade_group = QGroupBox("Grade selected written or programming answer")
        grade_form = QFormLayout(self.grade_group)
        self.grade_marks = QDoubleSpinBox()
        self.grade_marks.setRange(0, 10000)
        self.grade_marks.setDecimals(2)
        self.grade_feedback = QLineEdit()
        self.grade_feedback.setPlaceholderText("Optional feedback for the student")
        self.save_grade = QPushButton("Save Mark")
        style_action_button(self.save_grade, "primary")
        self.save_grade.clicked.connect(self.save_selected_grade)
        grade_form.addRow("Marks awarded", self.grade_marks)
        grade_form.addRow("Feedback", self.grade_feedback)
        grade_form.addRow("", self.save_grade)
        response_layout.addWidget(self.grade_group)
        root.addWidget(response_group, 1)

    def refresh_exams(self):
        try:
            selected = self.exam_picker.currentData()
            exams = get_submitted_exams(self.faculty_id)
            self.exam_picker.blockSignals(True)
            self.exam_picker.clear()
            for exam_id, title, course, status in exams:
                self.exam_picker.addItem(f"{title} · {course} · {status.title()}", exam_id)
            if selected is not None:
                index = self.exam_picker.findData(selected)
                if index >= 0:
                    self.exam_picker.setCurrentIndex(index)
            self.exam_picker.blockSignals(False)
            self.refresh_attempts()
        except Exception as error:
            self.exam_picker.blockSignals(False)
            QMessageBox.warning(self, "Could not load exams", str(error))

    def refresh_attempts(self, *_):
        exam_id = self.exam_picker.currentData()
        self.attempts_table.setRowCount(0)
        self.answers_table.setRowCount(0)
        self._questions = []
        self._selected_attempt = None
        self.grade_group.setEnabled(False)
        if exam_id is None:
            return
        try:
            rows = get_exam_attempts(self.faculty_id, int(exam_id))
            self.attempts_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                attempt_id, roll, name, submitted, status, marks, total, outcome = row
                values = (roll, name, submitted or "—", f"{float(marks):g} / {float(total):g}", outcome or "Pending review", attempt_id)
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if col == 5:
                        item.setData(Qt.ItemDataRole.UserRole, attempt_id)
                    self.attempts_table.setItem(row_index, col, item)
        except Exception as error:
            QMessageBox.warning(self, "Could not load submissions", str(error))

    def load_selected_attempt(self):
        row = self.attempts_table.currentRow()
        item = self.attempts_table.item(row, 5) if row >= 0 else None
        if item is None:
            return
        try:
            self._selected_attempt = int(item.data(Qt.ItemDataRole.UserRole))
            data = get_attempt_answers(self.faculty_id, self._selected_attempt)
            attempt = data["attempt"]
            self._questions = data["questions"]
            self.student_label.setText(
                f"{attempt['student']} · {attempt['roll_number']} · {attempt['exam']}"
            )
            self.answers_table.setRowCount(len(self._questions))
            for index, question in enumerate(self._questions, 1):
                maximum = float(question["max_marks"])
                awarded = question["marks_awarded"]
                values = (
                    index, question["type"].replace("_", " ").title(), question["prompt"],
                    _display(question["answer"]), _display(question["correct_answer"]),
                    (f"{float(awarded):g} / {maximum:g}" if awarded is not None else f"— / {maximum:g}"),
                    question["status"].replace("_", " ").title(),
                )
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setToolTip(str(value))
                    if col == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, question["id"])
                    self.answers_table.setItem(index - 1, col, cell)
            self.grade_group.setEnabled(True)
            if self._questions:
                self.answers_table.selectRow(0)
        except Exception as error:
            QMessageBox.warning(self, "Could not load answers", str(error))

    def select_question(self):
        row = self.answers_table.currentRow()
        if row < 0 or row >= len(self._questions):
            self.grade_group.setEnabled(False)
            return
        question = self._questions[row]
        manually_graded = question["type"] in {"short_answer", "descriptive", "programming"}
        self.grade_group.setEnabled(manually_graded)
        self.grade_marks.setMaximum(float(question["max_marks"]))
        self.grade_marks.setValue(float(question["marks_awarded"] or 0))
        self.grade_feedback.setText(question["feedback"])

    def save_selected_grade(self):
        row = self.answers_table.currentRow()
        if self._selected_attempt is None or row < 0 or row >= len(self._questions):
            return
        selected_attempt = self._selected_attempt
        question = self._questions[row]
        try:
            result = grade_exam_answer(
                self.faculty_id, selected_attempt, int(question["id"]),
                self.grade_marks.value(), self.grade_feedback.text(),
            )
            QMessageBox.information(
                self, "Mark saved",
                f"Score updated: {result['marks_awarded']:g} / {result['total_marks']:g}\n{result['outcome']}"
            )
            self.refresh_attempts()
            for r in range(self.attempts_table.rowCount()):
                if int(self.attempts_table.item(r, 5).data(Qt.ItemDataRole.UserRole)) == selected_attempt:
                    self.attempts_table.selectRow(r)
                    self.load_selected_attempt()
                    break
        except Exception as error:
            QMessageBox.warning(self, "Could not save mark", str(error))
