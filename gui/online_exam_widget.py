"""Faculty workspace for drafting, previewing, and publishing structured exams."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView,
)

from database.database import get_subjects, get_academic_classes
from exams.repository import (
    EXAM_TYPES, add_question_to_exam, create_exam, create_question,
    get_exam_preview, get_online_exam_catalog, publish_exam,
    remove_question_from_exam,
)
from gui.theme import POSITIVUS_QSS, create_section_header, style_action_button


class OnlineExamBuilderWidget(QWidget):
    """Faculty UI for structured exam setup and question authoring."""

    def __init__(self, faculty_id: int):
        super().__init__()
        self.faculty_id = faculty_id
        self.exam_id: int | None = None
        self._draft_editable = False
        self.classes = get_academic_classes(faculty_id=faculty_id)
        self._build_ui()
        self.refresh_exams()

    def _build_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(create_section_header(
            "Online Exam Builder", "Create a structured exam, add questions, preview it, then publish"
        ))

        existing_row = QHBoxLayout()
        self.exam_picker = QComboBox()
        self.exam_picker.setMinimumWidth(280)
        load_button = QPushButton("Load Exam")
        load_button.clicked.connect(self.load_selected_exam)
        new_button = QPushButton("New Draft")
        new_button.clicked.connect(self.new_draft)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_exams)
        existing_row.addWidget(QLabel("Your exams:"))
        existing_row.addWidget(self.exam_picker, 1)
        existing_row.addWidget(load_button)
        existing_row.addWidget(new_button)
        existing_row.addWidget(refresh_button)
        layout.addLayout(existing_row)

        details = QGroupBox("1. Exam details")
        details_form = QFormLayout(details)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Exam name")
        self.class_picker = QComboBox()
        for class_row in self.classes:
            self.class_picker.addItem(
                f"{class_row[1]} · Year {class_row[2]} · Section {class_row[3]} · {class_row[4]}",
                class_row[0],
            )
        self.class_picker.currentIndexChanged.connect(self._load_class_subjects)
        self.subject = QComboBox()
        self._load_class_subjects()
        self.exam_type = QComboBox()
        self.exam_type.addItems(EXAM_TYPES)
        self.duration = QSpinBox()
        self.duration.setRange(1, 1440)
        self.duration.setValue(60)
        self.duration.setSuffix(" min")
        self.passing_marks = QDoubleSpinBox()
        self.passing_marks.setRange(0, 10000)
        self.passing_marks.setDecimals(2)
        self.negative_marking = QCheckBox("Apply question penalties")
        self.negative_marking.toggled.connect(self._set_negative_marking_enabled)
        self.max_violations = QSpinBox()
        self.max_violations.setRange(1, 20)
        self.max_violations.setValue(3)
        self.randomize_questions = QCheckBox("Shuffle questions per student")
        self.randomize_options = QCheckBox("Shuffle answer options per student")
        self.schedule_enabled = QCheckBox("Schedule start and end time")
        schedule_row = QHBoxLayout()
        now = QDateTime.currentDateTime()
        self.starts_at = QDateTimeEdit(now.addSecs(300))
        self.starts_at.setCalendarPopup(True)
        self.ends_at = QDateTimeEdit(now.addSecs(3900))
        self.ends_at.setCalendarPopup(True)
        self.starts_at.setEnabled(False)
        self.ends_at.setEnabled(False)
        self.schedule_enabled.toggled.connect(self.starts_at.setEnabled)
        self.schedule_enabled.toggled.connect(self.ends_at.setEnabled)
        schedule_row.addWidget(QLabel("Starts"))
        schedule_row.addWidget(self.starts_at)
        schedule_row.addWidget(QLabel("Ends"))
        schedule_row.addWidget(self.ends_at)
        schedule_widget = QWidget()
        schedule_widget.setLayout(schedule_row)
        self.schedule_enabled.toggled.connect(schedule_widget.setVisible)
        schedule_widget.setVisible(False)

        details_form.addRow("Exam name", self.title)
        details_form.addRow("Class", self.class_picker)
        details_form.addRow("Subject", self.subject)
        details_form.addRow("Exam type", self.exam_type)
        details_form.addRow("Duration", self.duration)
        details_form.addRow("Passing marks", self.passing_marks)
        details_form.addRow("Negative marking", self.negative_marking)
        details_form.addRow("Violation limit", self.max_violations)
        details_form.addRow("Question order", self.randomize_questions)
        details_form.addRow("Option order", self.randomize_options)
        details_form.addRow("Schedule", self.schedule_enabled)
        details_form.addRow("", schedule_widget)
        create_row = QHBoxLayout()
        self.create_button = QPushButton("Create Draft Exam")
        style_action_button(self.create_button, "primary")
        self.create_button.clicked.connect(self.create_draft)
        self.active_label = QLabel("No exam draft selected")
        self.active_label.setWordWrap(True)
        create_row.addWidget(self.create_button)
        create_row.addWidget(self.active_label, 1)
        details_form.addRow("", self._layout_widget(create_row))
        layout.addWidget(details)

        question_group = QGroupBox("2. Add question to the selected draft")
        question_form = QFormLayout(question_group)
        self.question_type = QComboBox()
        self.question_type.addItems([
            "MCQ", "Multiple Select", "True/False", "Fill in the Blank",
            "Short Answer", "Descriptive", "Programming",
        ])
        self.question_prompt = QPlainTextEdit()
        self.question_prompt.setPlaceholderText("Question text")
        self.question_prompt.setMaximumHeight(90)
        self.question_marks = QDoubleSpinBox()
        self.question_marks.setRange(0.01, 10000)
        self.question_marks.setValue(1)
        self.question_marks.setDecimals(2)
        self.question_negative = QDoubleSpinBox()
        self.question_negative.setRange(0, 10000)
        self.question_negative.setDecimals(2)
        self.topic = QLineEdit()
        self.topic.setPlaceholderText("Optional topic")
        self.difficulty = QComboBox()
        self.difficulty.addItems(["Easy", "Medium", "Hard"])
        self.options = QPlainTextEdit()
        self.options.setPlaceholderText("One option per line. Prefix correct option(s) with *\nExample:\n*Binary search\nLinear search")
        self.options.setMaximumHeight(90)
        self.accepted_answers = QPlainTextEdit()
        self.accepted_answers.setPlaceholderText("Accepted answers, one per line (fill-in/auto-graded short answer)")
        self.accepted_answers.setMaximumHeight(65)
        self.matching_mode = QComboBox()
        self.matching_mode.addItem("Ignore letter case", "case_insensitive")
        self.matching_mode.addItem("Exact match", "exact")
        self.matching_mode.addItem("Ignore spaces and letter case", "whitespace_insensitive")
        self.auto_grade = QCheckBox("Automatically grade accepted short answers")
        self.language = QComboBox()
        self.language.addItems(["Python", "Java", "C", "C++"])
        self.starter_code = QPlainTextEdit()
        self.starter_code.setPlaceholderText("Optional starter code")
        self.starter_code.setMaximumHeight(80)
        self.input_format = QLineEdit()
        self.output_format = QLineEdit()
        self.constraints = QLineEdit()
        self.test_cases = QPlainTextEdit()
        self.test_cases.setPlaceholderText(
            'Programming test cases as JSON, e.g. [{"input":"3\\n1 2 3\\n","expected_output":"3","is_hidden":true}]'
        )
        self.test_cases.setMaximumHeight(90)
        self.question_type.currentTextChanged.connect(self._update_question_fields)
        question_form.addRow("Type", self.question_type)
        question_form.addRow("Question", self.question_prompt)
        question_form.addRow("Marks", self.question_marks)
        question_form.addRow("Negative marks", self.question_negative)
        question_form.addRow("Topic", self.topic)
        question_form.addRow("Difficulty", self.difficulty)
        question_form.addRow("Options", self.options)
        question_form.addRow("Accepted answers", self.accepted_answers)
        question_form.addRow("Text matching", self.matching_mode)
        question_form.addRow("Short answer grading", self.auto_grade)
        question_form.addRow("Programming language", self.language)
        question_form.addRow("Starter code", self.starter_code)
        question_form.addRow("Input format", self.input_format)
        question_form.addRow("Output format", self.output_format)
        question_form.addRow("Constraints", self.constraints)
        question_form.addRow("Sample and hidden tests", self.test_cases)
        add_button = QPushButton("Add Question")
        style_action_button(add_button, "secondary")
        add_button.clicked.connect(self.add_question)
        question_form.addRow("", add_button)
        layout.addWidget(question_group)

        layout.addWidget(QLabel("3. Draft questions"))
        self.questions_table = QTableWidget(0, 4)
        self.questions_table.setHorizontalHeaderLabels(["#", "Type", "Question", "Marks"])
        self.questions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.questions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.questions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.questions_table.setMaximumHeight(210)
        layout.addWidget(self.questions_table)
        actions = QHBoxLayout()
        self.remove_question_button = QPushButton("Remove Selected Question")
        self.remove_question_button.clicked.connect(self.remove_selected_question)
        self.preview_button = QPushButton("Preview Exam")
        self.preview_button.clicked.connect(self.preview_exam)
        self.publish_button = QPushButton("Publish Exam")
        style_action_button(self.publish_button, "primary")
        self.publish_button.clicked.connect(self.publish_current_exam)
        actions.addWidget(self.remove_question_button)
        actions.addWidget(self.preview_button)
        actions.addWidget(self.publish_button)
        actions.addStretch()
        layout.addLayout(actions)
        self._update_question_fields(self.question_type.currentText())
        self._set_exam_state(None, "No exam draft selected")

    @staticmethod
    def _layout_widget(layout):
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _load_class_subjects(self, *_):
        if not hasattr(self, "subject"):
            return
        selected = self.subject.currentData()
        class_id = self.class_picker.currentData()
        self.subject.clear()
        if class_id is not None:
            for subject_id, code, name in get_subjects(faculty_id=self.faculty_id, class_id=int(class_id)):
                self.subject.addItem(f"{code} — {name}", subject_id)
        index = self.subject.findData(selected)
        if index >= 0:
            self.subject.setCurrentIndex(index)

    def _update_question_fields(self, label: str):
        kind = label.casefold()
        objective = kind in {"mcq", "multiple select", "true/false"}
        fill = kind == "fill in the blank"
        short = kind == "short answer"
        programming = kind == "programming"
        self.options.setVisible(objective)
        self.accepted_answers.setVisible(fill or short)
        self.matching_mode.setVisible(fill or short)
        self.auto_grade.setVisible(short)
        for widget in (self.language, self.starter_code, self.input_format, self.output_format,
                       self.constraints, self.test_cases):
            widget.setVisible(programming)
        self._set_negative_marking_enabled(self.negative_marking.isChecked())

    def _set_negative_marking_enabled(self, enabled: bool):
        self.question_negative.setEnabled(enabled)

    def refresh_exams(self, select_id: int | None = None):
        try:
            rows = get_online_exam_catalog(self.faculty_id)
        except Exception as error:
            QMessageBox.warning(self, "Could not load exams", str(error))
            return
        self.exam_picker.clear()
        for exam_row in rows:
            exam_id, code, title, exam_type, duration, status, total, start, end, department, year, section, academic_year = exam_row
            class_label = f"{department} · Year {year} · {section} · {academic_year}" if department else "No class"
            label = f"{title} — {code} — {class_label} — {status.title()}"
            self.exam_picker.addItem(label, exam_id)
        if select_id is not None:
            index = self.exam_picker.findData(select_id)
            if index >= 0:
                self.exam_picker.setCurrentIndex(index)

    def load_selected_exam(self):
        exam_id = self.exam_picker.currentData()
        if exam_id is None:
            return
        try:
            preview = get_exam_preview(self.faculty_id, int(exam_id))
        except Exception as error:
            QMessageBox.warning(self, "Could not load exam", str(error))
            return
        exam = preview["exam"]
        self.exam_id = int(exam_id)
        self.active_label.setText(f"Selected: {exam['title']} · {exam['status'].title()}")
        editable = exam["status"] == "draft"
        self._draft_editable = editable
        type_to_question = {
            "MCQ": "MCQ", "Multiple Select": "Multiple Select",
            "True/False": "True/False", "Fill in the Blank": "Fill in the Blank",
            "Short Answer": "Short Answer", "Descriptive": "Descriptive",
            "Programming": "Programming",
        }
        self.question_type.setEnabled(editable and exam["exam_type"] == "Mixed")
        if exam["exam_type"] in type_to_question:
            self.question_type.setCurrentText(type_to_question[exam["exam_type"]])
        self.title.setText(exam["title"])
        if exam.get("class_id") is not None:
            self.class_picker.setCurrentIndex(self.class_picker.findData(exam["class_id"]))
        self._load_class_subjects()
        self.subject.setCurrentIndex(self.subject.findData(exam["subject_id"]))
        self.exam_type.setCurrentText(exam["exam_type"])
        self.duration.setValue(int(exam["duration_minutes"]))
        self.passing_marks.setValue(float(exam["passing_marks"]))
        self.negative_marking.setChecked(bool(exam["negative_marking"]))
        self.max_violations.setValue(int(exam["max_violations"]))
        self.randomize_questions.setChecked(bool(exam["randomize_questions"]))
        self.randomize_options.setChecked(bool(exam["randomize_options"]))
        self.schedule_enabled.setChecked(bool(exam["starts_at"] and exam["ends_at"]))
        if exam["starts_at"]:
            self.starts_at.setDateTime(QDateTime.fromString(exam["starts_at"], Qt.DateFormat.ISODate))
        if exam["ends_at"]:
            self.ends_at.setDateTime(QDateTime.fromString(exam["ends_at"], Qt.DateFormat.ISODate))
        self.title.setEnabled(False)
        self.subject.setEnabled(False)
        self.class_picker.setEnabled(False)
        self.exam_type.setEnabled(False)
        self.duration.setEnabled(False)
        self.passing_marks.setEnabled(False)
        self.negative_marking.setEnabled(False)
        self.max_violations.setEnabled(False)
        self.randomize_questions.setEnabled(False)
        self.randomize_options.setEnabled(False)
        self.schedule_enabled.setEnabled(False)
        self.create_button.setEnabled(False)
        self.question_type.setEnabled(editable and exam["exam_type"] == "Mixed")
        self.question_prompt.setEnabled(editable)
        self.question_marks.setEnabled(editable)
        self.question_negative.setEnabled(editable)
        self.add_question_button_state(editable)
        self.publish_button.setEnabled(editable and bool(preview["questions"]))
        self._show_questions(preview["questions"])

    def new_draft(self):
        self.exam_id = None
        self._draft_editable = False
        self.active_label.setText("Creating a new exam draft")
        self.title.clear()
        self.exam_type.setCurrentText("Mixed")
        self.duration.setValue(60)
        self.passing_marks.setValue(0)
        self.negative_marking.setChecked(False)
        self.max_violations.setValue(3)
        self.randomize_questions.setChecked(False)
        self.randomize_options.setChecked(False)
        self.schedule_enabled.setChecked(False)
        self.title.setEnabled(True)
        self.subject.setEnabled(True)
        self.class_picker.setEnabled(True)
        self.question_type.setEnabled(True)
        self.exam_type.setEnabled(True)
        self.duration.setEnabled(True)
        self.passing_marks.setEnabled(True)
        self.negative_marking.setEnabled(True)
        self.max_violations.setEnabled(True)
        self.randomize_questions.setEnabled(True)
        self.randomize_options.setEnabled(True)
        self.schedule_enabled.setEnabled(True)
        self.create_button.setEnabled(True)
        self.add_question_button_state(False)
        self.remove_question_button.setEnabled(False)
        self.questions_table.setRowCount(0)
        self.publish_button.setEnabled(False)
        self.preview_button.setEnabled(False)

    def add_question_button_state(self, enabled: bool):
        for widget in (self.topic, self.difficulty, self.options, self.accepted_answers,
                       self.matching_mode, self.auto_grade, self.language, self.starter_code,
                       self.input_format, self.output_format, self.constraints, self.test_cases):
            widget.setEnabled(enabled)
        for button in self.findChildren(QPushButton):
            if button.text() == "Add Question":
                button.setEnabled(enabled)

    def _set_exam_state(self, exam_id: int | None, label: str):
        self.exam_id = exam_id
        self.active_label.setText(label)
        self.publish_button.setEnabled(False)
        self.preview_button.setEnabled(exam_id is not None)
        self.questions_table.setRowCount(0)

    def create_draft(self):
        subject_id = self.subject.currentData()
        if subject_id is None:
            QMessageBox.warning(self, "Create exam", "Add or select a course first.")
            return
        class_id = self.class_picker.currentData()
        if class_id is None:
            QMessageBox.warning(self, "Create exam", "Create or select an academic class first.")
            return
        start = end = None
        if self.schedule_enabled.isChecked():
            start = self.starts_at.dateTime().toUTC().toString(Qt.DateFormat.ISODate)
            end = self.ends_at.dateTime().toUTC().toString(Qt.DateFormat.ISODate)
        try:
            exam_id = create_exam(
                self.faculty_id, int(subject_id), self.title.text(),
                exam_type=self.exam_type.currentText(), duration_minutes=self.duration.value(),
                passing_marks=self.passing_marks.value(), starts_at=start, ends_at=end,
                negative_marking=self.negative_marking.isChecked(),
                max_violations=self.max_violations.value(),
                randomize_questions=self.randomize_questions.isChecked(),
                randomize_options=self.randomize_options.isChecked(),
                class_id=int(class_id),
            )
        except Exception as error:
            QMessageBox.warning(self, "Could not create exam", str(error))
            return
        self.title.clear()
        self.refresh_exams(exam_id)
        self.load_selected_exam()

    def add_question(self):
        if self.exam_id is None:
            QMessageBox.information(self, "Select a draft", "Create or load a draft exam before adding questions.")
            return
        kind = self.question_type.currentText().casefold()
        expected_types = {
            "MCQ": "mcq", "Multiple Select": "multiple select",
            "True/False": "true/false", "Fill in the Blank": "fill in the blank",
            "Short Answer": "short answer", "Descriptive": "descriptive",
            "Programming": "programming",
        }
        expected = expected_types.get(self.exam_type.currentText())
        if expected and kind != expected:
            QMessageBox.warning(self, "Question type", f"This is a {self.exam_type.currentText()} exam. Its question type has been set to match.")
            self.question_type.setCurrentText(expected.title())
            return
        data = {
            "question_type": kind,
            "prompt": self.question_prompt.toPlainText(),
            "marks": self.question_marks.value(),
            "negative_marks": self.question_negative.value() if self.negative_marking.isChecked() else 0,
            "topic": self.topic.text(),
            "difficulty": self.difficulty.currentText(),
            "matching_mode": self.matching_mode.currentData(),
            "auto_grade": self.auto_grade.isChecked(),
        }
        if kind in {"mcq", "multiple select"}:
            data["options"] = [
                {"text": line.lstrip("* ").strip(), "is_correct": line.lstrip()[:1] == "*"}
                for line in self.options.toPlainText().splitlines() if line.strip()
            ]
        elif kind == "true/false":
            option_lines = [line.strip() for line in self.options.toPlainText().splitlines() if line.strip()]
            if option_lines:
                data["options"] = [
                    {"text": line.lstrip("* ").strip(), "is_correct": line.lstrip()[:1] == "*"}
                    for line in option_lines
                ]
            else:
                data["correct_answer"] = "True"
        elif kind in {"fill in the blank", "short answer"}:
            data["accepted_answers"] = [
                line.strip() for line in self.accepted_answers.toPlainText().splitlines() if line.strip()
            ]
        elif kind == "programming":
            data.update({
                "programming_language": self.language.currentText(),
                "starter_code": self.starter_code.toPlainText(),
                "input_format": self.input_format.text(), "output_format": self.output_format.text(),
                "constraints": self.constraints.text(),
            })
            try:
                data["test_cases"] = json.loads(self.test_cases.toPlainText())
            except json.JSONDecodeError as error:
                QMessageBox.warning(self, "Test cases", f"Enter test cases as valid JSON: {error}")
                return
        try:
            subject_id = int(self.subject.currentData())
            question_id = create_question(self.faculty_id, subject_id, data)
            add_question_to_exam(self.faculty_id, self.exam_id, question_id)
            self.question_prompt.clear()
            self.options.clear()
            self.accepted_answers.clear()
            self.test_cases.clear()
            self.load_selected_exam()
        except Exception as error:
            QMessageBox.warning(self, "Could not add question", str(error))

    def _show_questions(self, questions):
        self.questions_table.setRowCount(len(questions))
        for row, question in enumerate(questions):
            values = (question["question_order"], question["question_type"].replace("_", " ").title(),
                      question["prompt"], question["marks_override"] or question["marks"])
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, question["id"])
                self.questions_table.setItem(row, column, item)
        is_draft = self.exam_id is not None and self._draft_editable
        self.remove_question_button.setEnabled(is_draft and bool(questions))

    def remove_selected_question(self):
        if self.exam_id is None:
            return
        row = self.questions_table.currentRow()
        item = self.questions_table.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(self, "Select a question", "Select a question row to remove it from this draft.")
            return
        try:
            remove_question_from_exam(
                self.faculty_id, self.exam_id, int(item.data(Qt.ItemDataRole.UserRole))
            )
            self.load_selected_exam()
        except Exception as error:
            QMessageBox.warning(self, "Could not remove question", str(error))

    def _load_preview(self):
        if self.exam_id is None:
            raise ValueError("Create or select an exam draft first.")
        return get_exam_preview(self.faculty_id, self.exam_id)

    def preview_exam(self):
        try:
            data = self._load_preview()
        except Exception as error:
            QMessageBox.warning(self, "Could not preview exam", str(error))
            return
        exam = data["exam"]
        if not data["questions"]:
            QMessageBox.information(self, "Exam preview", "Add questions before previewing this exam.")
            return
        lines = [f"{exam['title']} · {exam['exam_type']} · {exam['duration_minutes']} minutes", ""]
        for index, question in enumerate(data["questions"], start=1):
            lines.append(f"{index}. {question['prompt']} ({question['marks_override'] or question['marks']} marks)")
            for order, option, correct in question["options"]:
                lines.append(f"   {'✓ ' if correct else ''}{order}. {option}")
            if question["accepted_answers"]:
                lines.append(f"   Accepted: {question['accepted_answers']}")
            if question["question_type"] == "programming":
                visible = sum(1 for case in question["test_cases"] if not case[3])
                hidden = sum(1 for case in question["test_cases"] if case[3])
                lines.append(f"   Test cases: {visible} sample, {hidden} hidden")
            lines.append("")
        QMessageBox.information(self, "Exam preview", "\n".join(lines))

    def publish_current_exam(self):
        if self.exam_id is None:
            return
        try:
            preview = self._load_preview()
            total = sum(float(q["marks_override"] or q["marks"]) for q in preview["questions"])
        except Exception as error:
            QMessageBox.warning(self, "Publish exam", str(error))
            return
        answer = QMessageBox.question(
            self, "Publish exam",
            f"Publish '{preview['exam']['title']}' with {len(preview['questions'])} question(s) for {total:g} marks?\n\nPublished questions and answer keys will be used to grade student attempts.",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            total = publish_exam(self.faculty_id, self.exam_id)
            QMessageBox.information(self, "Exam published", f"Exam published successfully. Total: {total:g} marks.")
            self.refresh_exams(self.exam_id)
            self.load_selected_exam()
        except Exception as error:
            QMessageBox.warning(self, "Could not publish exam", str(error))
