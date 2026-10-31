"""Student exam list and focused, timed online-exam attempt interface."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QRadioButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from exams.attempts import get_student_exam_catalog, save_answer, start_attempt, submit_attempt
from gui.theme import create_section_header, style_action_button


class OnlineStudentExamWidget(QWidget):
    """A student can view eligible exams, start/resume, autosave, and submit."""

    def __init__(self, user, dashboard):
        super().__init__()
        self.user = user
        self.dashboard = dashboard
        self.exams = []
        self.attempt = None
        self.questions = []
        self.question_index = 0
        self.answer_editor = None
        self.answer_controls = []
        self.answers = {}
        self._saving = False
        self.setStyleSheet("QLabel { color: #26323B; }")
        self._build_ui()
        self.refresh_exams()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        root.addWidget(create_section_header("Online Examinations", "Available exams, saved attempts, and results"))

        self.list_panel = QWidget()
        list_layout = QVBoxLayout(self.list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(QLabel("Select an available exam to read its instructions and begin."))
        self.exam_table = QTableWidget(0, 7)
        self.exam_table.setHorizontalHeaderLabels(["Course", "Exam", "Type", "Time", "Marks", "Status", "Result"])
        self.exam_table.horizontalHeader().setStretchLastSection(True)
        self.exam_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.exam_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.exam_table.itemSelectionChanged.connect(self._update_start_button)
        list_layout.addWidget(self.exam_table, 1)
        actions = QHBoxLayout()
        refresh = QPushButton("Refresh Exams")
        refresh.clicked.connect(self.refresh_exams)
        self.start_button = QPushButton("Start / Resume Exam")
        style_action_button(self.start_button, "primary")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_selected_exam)
        actions.addWidget(refresh)
        actions.addStretch()
        actions.addWidget(self.start_button)
        list_layout.addLayout(actions)
        self.list_panel.setLayout(list_layout)
        root.addWidget(self.list_panel, 1)

        self.exam_panel = QWidget()
        exam_layout = QVBoxLayout(self.exam_panel)
        exam_layout.setContentsMargins(0, 0, 0, 0)
        exam_header = QHBoxLayout()
        self.exam_title = QLabel("Exam")
        self.exam_title.setStyleSheet("font-size: 17px; font-weight: 700;")
        self.timer_label = QLabel("Time remaining: --:--")
        self.timer_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #36566B;")
        exam_header.addWidget(self.exam_title, 1)
        exam_header.addWidget(self.timer_label)
        exam_layout.addLayout(exam_header)
        self.save_status = QLabel("Your answers save automatically.")
        self.save_status.setWordWrap(True)
        exam_layout.addWidget(self.save_status)
        self.question_count = QLabel("")
        self.question_count.setStyleSheet("font-weight: 600;")
        exam_layout.addWidget(self.question_count)
        self.prompt = QLabel("")
        self.prompt.setWordWrap(True)
        self.prompt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.prompt.setStyleSheet("font-size: 16px; font-weight: 600; padding: 12px; background: #FFFFFF; border: 1px solid #DCE2E7; border-radius: 8px;")
        exam_layout.addWidget(self.prompt)
        self.question_details = QLabel("")
        self.question_details.setWordWrap(True)
        exam_layout.addWidget(self.question_details)
        self.answer_area = QWidget()
        self.answer_layout = QVBoxLayout(self.answer_area)
        self.answer_layout.setContentsMargins(0, 0, 0, 0)
        exam_layout.addWidget(self.answer_area, 1)
        navigation = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.previous_button.clicked.connect(lambda: self.show_question(self.question_index - 1))
        self.answer_status = QLabel("")
        self.answer_status.setAlignment(Qt.AlignCenter)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(lambda: self.show_question(self.question_index + 1))
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.answer_status, 1)
        navigation.addWidget(self.next_button)
        exam_layout.addLayout(navigation)
        footer = QHBoxLayout()
        self.exit_button = QPushButton("Return to exam list")
        self.exit_button.clicked.connect(self.return_to_list)
        self.submit_button = QPushButton("Submit Exam")
        style_action_button(self.submit_button, "primary")
        self.submit_button.clicked.connect(self.confirm_submit)
        footer.addWidget(self.exit_button)
        footer.addStretch()
        footer.addWidget(self.submit_button)
        exam_layout.addLayout(footer)
        self.exam_panel.hide()
        root.addWidget(self.exam_panel, 1)

        self.countdown = QTimer(self)
        self.countdown.setInterval(1000)
        self.countdown.timeout.connect(self._tick)
        self.autosave = QTimer(self)
        self.autosave.setInterval(5000)
        self.autosave.timeout.connect(self._save_current)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(700)
        self.debounce.timeout.connect(self._save_current)

    def refresh_exams(self):
        try:
            self.exams = get_student_exam_catalog(self.user[0])
        except Exception as error:
            QMessageBox.warning(self, "Could not load exams", str(error))
            self.exams = []
        self.exam_table.setRowCount(len(self.exams))
        for row, exam in enumerate(self.exams):
            values = (
                exam["subject_code"], exam["title"], exam["exam_type"],
                f"{exam['duration_minutes']} min", f"{exam['total_marks']:g}", exam["status"],
                (f"{exam['result_outcome']} · {exam['result_marks']:g}/{exam['result_total']:g}"
                 if exam["result_outcome"] and exam["result_marks"] is not None else "—"),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.UserRole, exam["id"])
                self.exam_table.setItem(row, column, cell)
        self._update_start_button()

    def _selected_exam(self):
        row = self.exam_table.currentRow()
        return self.exams[row] if 0 <= row < len(self.exams) else None

    def _update_start_button(self):
        exam = self._selected_exam()
        self.start_button.setEnabled(bool(exam and exam["status"] in {"Available", "In progress"}))
        if exam and exam["status"] == "In progress":
            self.start_button.setText("Resume Exam")
        else:
            self.start_button.setText("Start Exam")

    def start_selected_exam(self):
        exam = self._selected_exam()
        if not exam:
            return
        instructions = (
            f"{exam['title']}\n\nCourse: {exam['subject_code']} · {exam['exam_type']}\n"
            f"Duration: {exam['duration_minutes']} minutes · Total: {exam['total_marks']:g} marks\n\n"
            "The exam opens full screen. Your timer starts when you continue, and answers save automatically. "
            "EduPilot can restrict navigation inside the app, but cannot block operating-system shortcuts or other devices."
        )
        choice = QMessageBox.question(
            self, "Exam instructions", instructions,
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
        )
        if choice != QMessageBox.Yes:
            return
        self.dashboard.switch_page(self.dashboard.ONLINE_EXAM_PAGE_INDEX)
        self.dashboard.sidebar.hide()
        self.dashboard.showFullScreen()
        try:
            attempt = start_attempt(self.user[0], int(exam["id"]))
        except Exception as error:
            self.dashboard.sidebar.show()
            self.dashboard.showMaximized()
            QMessageBox.warning(self, "Could not start exam", str(error))
            self.refresh_exams()
            return
        self.dashboard._exam_active = True
        self.dashboard._active_exam_page_index = self.dashboard.ONLINE_EXAM_PAGE_INDEX
        self.attempt = attempt
        self.questions = attempt["questions"]
        self.answers = {question["id"]: question["answer"] for question in self.questions}
        self._saved_answers = dict(self.answers)
        self.question_index = 0
        self.exam_title.setText(attempt["title"])
        self.list_panel.hide()
        self.exam_panel.show()
        self._show_question(0)
        self._update_timer_label()
        self.countdown.start()
        self.autosave.start()

    def _show_question(self, index: int):
        while self.answer_layout.count():
            item = self.answer_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.answer_controls = []
        self.answer_editor = None
        if not self.questions:
            self.prompt.setText("No questions are available. Contact faculty.")
            self.question_count.setText("")
            return
        self.question_index = max(0, min(index, len(self.questions) - 1))
        question = self.questions[self.question_index]
        self.current_question = question
        self.question_count.setText(
            f"Question {self.question_index + 1} of {len(self.questions)} · {question['marks']:g} marks"
        )
        self.prompt.setText(question["prompt"])
        detail_parts = []
        if question.get("topic"):
            detail_parts.append(str(question["topic"]))
        if question["question_type"] == "programming":
            detail_parts.extend((
                f"Language: {question['programming_language']}",
                f"Limits: {question['time_limit_seconds']} sec · {question['memory_limit_mb']} MB",
            ))
            if question.get("input_format"):
                detail_parts.append("Input: " + question["input_format"])
            if question.get("output_format"):
                detail_parts.append("Output: " + question["output_format"])
            if question.get("constraints"):
                detail_parts.append("Constraints: " + question["constraints"])
            for i, sample in enumerate(question.get("sample_cases", []), 1):
                detail_parts.append(f"Sample {i} input:\n{sample['input']}\nExpected output:\n{sample['expected_output']}")
        self.question_details.setText("\n".join(detail_parts))
        kind = question["question_type"]
        answer = self.answers.get(question["id"])
        if kind in {"mcq", "true_false"}:
            for option in question["options"]:
                control = QRadioButton(option["text"])
                control.setProperty("answer_order", option["order"])
                control.setChecked(answer is not None and str(answer) == str(option["order"]))
                control.toggled.connect(lambda checked: checked and self._answer_changed())
                self.answer_layout.addWidget(control)
                self.answer_controls.append(control)
        elif kind == "multiple_select":
            selected = {str(value) for value in (answer or [])}
            for option in question["options"]:
                control = QCheckBox(option["text"])
                control.setProperty("answer_order", option["order"])
                control.setChecked(str(option["order"]) in selected)
                control.toggled.connect(self._answer_changed)
                self.answer_layout.addWidget(control)
                self.answer_controls.append(control)
        elif kind == "fill_blank":
            control = QLineEdit()
            control.setPlaceholderText("Type your answer")
            control.setText(str(answer or ""))
            control.textChanged.connect(lambda _text: self._answer_changed())
            self.answer_layout.addWidget(control)
            self.answer_editor = control
        else:
            control = QPlainTextEdit()
            control.setPlaceholderText("Type your answer" if kind != "programming" else "Write your program")
            if kind == "programming" and question.get("starter_code") and not answer:
                answer = question["starter_code"]
            if isinstance(answer, dict) and "source" in answer:
                answer = answer["source"]
            control.setPlainText(str(answer or ""))
            control.setMinimumHeight(220 if kind == "programming" else 140)
            control.textChanged.connect(self._answer_changed)
            self.answer_layout.addWidget(control, 1)
            self.answer_editor = control
        self.previous_button.setEnabled(self.question_index > 0)
        self.next_button.setEnabled(self.question_index < len(self.questions) - 1)
        self.answer_status.setText("Answered" if self._has_answer(question["id"]) else "Not answered")

    def show_question(self, index: int):
        self._save_current()
        self._show_question(index)

    def _read_answer(self):
        question = self.current_question
        kind = question["question_type"]
        if kind in {"mcq", "true_false"}:
            selected = next((control for control in self.answer_controls if control.isChecked()), None)
            if selected is None:
                return None
            if kind == "true_false":
                return selected.text().strip().casefold() == "true"
            return int(selected.property("answer_order"))
        if kind == "multiple_select":
            return [int(control.property("answer_order")) for control in self.answer_controls if control.isChecked()]
        if self.answer_editor is None:
            return None
        if kind == "fill_blank":
            return self.answer_editor.text()
        text = self.answer_editor.toPlainText()
        if kind == "programming":
            return {"language": question["programming_language"], "source": text}
        return text

    def _answer_changed(self):
        if not self.attempt or self._saving:
            return
        self.answers[self.current_question["id"]] = self._read_answer()
        self.answer_status.setText("Saving…")
        self.debounce.start()

    def _has_answer(self, question_id):
        value = self.answers.get(question_id)
        return value is not None and value != "" and value != [] and value != {}

    def _save_current(self):
        if not self.attempt or not self.questions or not hasattr(self, "current_question"):
            return
        question = self.current_question
        answer = self._read_answer()
        if self._saved_answers.get(question["id"], object()) == answer:
            return
        self.answers[question["id"]] = answer
        try:
            save_answer(self.user[0], self.attempt["id"], question["id"], answer)
            self._saved_answers[question["id"]] = answer
            self.save_status.setText("All answers are saved automatically.")
            self.answer_status.setText("Answered" if self._has_answer(question["id"]) else "Not answered")
        except Exception as error:
            self.save_status.setText(f"Could not save this answer: {error}")

    def _update_timer_label(self):
        remaining = max(0, int(self.attempt.get("seconds_remaining", 0)))
        minutes, seconds = divmod(remaining, 60)
        self.timer_label.setText(f"Time remaining: {minutes:02d}:{seconds:02d}")

    def _tick(self):
        if not self.attempt:
            return
        self.attempt["seconds_remaining"] = max(0, int(self.attempt.get("seconds_remaining", 0)) - 1)
        self._update_timer_label()
        if self.attempt["seconds_remaining"] <= 0:
            self.countdown.stop()
            self.autosave.stop()
            self.debounce.stop()
            self._save_current()
            self._submit_expired()

    def confirm_submit(self):
        if not self.attempt:
            return
        self._save_current()
        unanswered = sum(not self._has_answer(question["id"]) for question in self.questions)
        prompt = "Submit your exam now? You cannot change answers after submission."
        if unanswered:
            prompt += f"\n\n{unanswered} question(s) have no answer."
        answer = QMessageBox.question(
            self, "Submit exam", prompt,
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
        )
        if answer == QMessageBox.Yes:
            try:
                result = submit_attempt(self.user[0], self.attempt["id"])
            except ValueError as error:
                if "expired" not in str(error).casefold():
                    QMessageBox.warning(self, "Could not submit", str(error))
                    return
                result = submit_attempt(self.user[0], self.attempt["id"], allow_expired=True)
            except Exception as error:
                QMessageBox.warning(self, "Could not submit", str(error))
                return
            self._finish_attempt(result)

    def _submit_expired(self):
        try:
            result = submit_attempt(self.user[0], self.attempt["id"], allow_expired=True)
            self._finish_attempt(result)
        except Exception as error:
            self.save_status.setText(f"Time expired; automatic submission needs attention: {error}")
            self.submit_button.setText("Retry automatic submission")

    def _finish_attempt(self, result):
        self.countdown.stop()
        self.autosave.stop()
        self.debounce.stop()
        self.dashboard._exam_active = False
        self.dashboard._active_exam_page_index = None
        self.exam_panel.hide()
        self.list_panel.show()
        self.dashboard.sidebar.show()
        self.dashboard.showMaximized()
        if result["outcome"] == "Pending review":
            message = f"Submitted. Some answers need faculty review. Automatically scored: {result['marks_awarded']:g}/{result['total_marks']:g}."
        else:
            message = f"Submitted. Score: {result['marks_awarded']:g}/{result['total_marks']:g} · {result['outcome']}."
        QMessageBox.information(self, "Exam submitted", message)
        self.attempt = None
        self.questions = []
        self.answers = {}
        self._saved_answers = {}
        self.refresh_exams()

    def return_to_list(self):
        if self.attempt:
            QMessageBox.information(self, "Exam in progress", "Your timed attempt is active. Submit it or wait for automatic submission before leaving.")
            return
        self.list_panel.show()
        self.exam_panel.hide()

