from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QTextEdit,
)

from database.database import (get_subjects, get_lab_exam_catalog, publish_lab_exam,
                               close_lab_exam, get_lab_exam_submissions)
from gui.theme import POSITIVUS_QSS, create_section_header, style_action_button


class FacultyLabExamWidget(QWidget):
    """Publish and close practical exams using the faculty account's permissions."""
    def __init__(self, faculty_id: int):
        super().__init__()
        self.faculty_id = faculty_id
        self.setStyleSheet(POSITIVUS_QSS)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        layout.addWidget(create_section_header("Practical Exam Management", "Publish one active exam for students; submissions use its fixed time limit"))

        subject_row = QHBoxLayout()
        self.subject = QComboBox()
        for sid, code, name in get_subjects():
            self.subject.addItem(f"{code} — {name}", sid)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Exam title")
        self.duration = QSpinBox()
        self.duration.setRange(1, 240)
        self.duration.setValue(60)
        self.duration.setSuffix(" min")
        subject_row.addWidget(self.subject, 2)
        subject_row.addWidget(self.title, 2)
        subject_row.addWidget(QLabel("Duration:"))
        subject_row.addWidget(self.duration)
        layout.addLayout(subject_row)

        self.paper = QTextEdit()
        self.paper.setPlaceholderText("Question paper and practical instructions")
        self.paper.setMinimumHeight(120)
        layout.addWidget(self.paper)

        actions = QHBoxLayout()
        publish = QPushButton("Publish Exam")
        style_action_button(publish, "primary")
        publish.clicked.connect(self._publish)
        close = QPushButton("Close Selected Active Exam")
        style_action_button(close, "outline")
        close.clicked.connect(self._close_selected)
        actions.addWidget(publish)
        actions.addWidget(close)
        actions.addStretch()
        layout.addLayout(actions)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Subject", "Exam", "Duration", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._load_submissions)
        layout.addWidget(self.table, 1)

        layout.addWidget(QLabel("Student submissions for selected exam"))
        self.submissions = QTableWidget(0, 4)
        self.submissions.setHorizontalHeaderLabels(["Roll Number", "Student", "Started", "Submitted"])
        self.submissions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.submissions.setSelectionBehavior(QTableWidget.SelectRows)
        self.submissions.setEditTriggers(QTableWidget.NoEditTriggers)
        self.submissions.itemSelectionChanged.connect(self._show_solution)
        layout.addWidget(self.submissions)
        self.solution = QTextEdit()
        self.solution.setReadOnly(True)
        self.solution.setPlaceholderText("Select a student submission to review its saved solution.")
        self.solution.setMinimumHeight(120)
        layout.addWidget(self.solution)

    def refresh(self):
        rows = get_lab_exam_catalog()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            exam_id, code, subject, title, duration, active, created = row
            values = (exam_id, f"{code} — {subject}", title, f"{duration} min", "Active" if active else "Closed")
            for col, value in enumerate(values):
                self.table.setItem(index, col, QTableWidgetItem(str(value)))
        self.submissions.setRowCount(0)
        self.solution.clear()

    def _load_submissions(self):
        row = self.table.currentRow()
        if row < 0:
            return
        exam_id = int(self.table.item(row, 0).text())
        try:
            self.current_submissions = get_lab_exam_submissions(exam_id, self.faculty_id)
            self.submissions.setRowCount(len(self.current_submissions))
            for index, entry in enumerate(self.current_submissions):
                roll, name, started, submitted, solution = entry
                for column, value in enumerate((roll, name, started, submitted or "In progress")):
                    self.submissions.setItem(index, column, QTableWidgetItem(str(value or "—")))
            self.solution.clear()
        except Exception as error:
            QMessageBox.critical(self, "Could not load submissions", str(error))

    def _show_solution(self):
        row = self.submissions.currentRow()
        if 0 <= row < len(getattr(self, "current_submissions", [])):
            self.solution.setPlainText(self.current_submissions[row][4])

    def _publish(self):
        subject_id = self.subject.currentData()
        if not subject_id:
            QMessageBox.warning(self, "Publish exam", "Add or select a course first.")
            return
        try:
            exam_id = publish_lab_exam(subject_id, self.title.text(), self.paper.toPlainText(),
                                       self.duration.value(), self.faculty_id)
            QMessageBox.information(self, "Exam published", f"Exam {exam_id} is now active for students.")
            self.title.clear()
            self.paper.clear()
            self.refresh()
        except Exception as error:
            QMessageBox.critical(self, "Could not publish exam", str(error))

    def _close_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Close exam", "Select an exam row first.")
            return
        exam_id = int(self.table.item(row, 0).text())
        try:
            if not close_lab_exam(exam_id, self.faculty_id):
                QMessageBox.information(self, "Close exam", "That exam is already closed.")
            else:
                QMessageBox.information(self, "Exam closed", "Students can no longer start or submit this exam.")
            self.refresh()
        except Exception as error:
            QMessageBox.critical(self, "Could not close exam", str(error))
