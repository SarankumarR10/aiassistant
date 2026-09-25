from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox,
)

from database.database import get_lab_submission_reviews, review_lab_submission
from gui.theme import POSITIVUS_QSS, create_section_header, style_action_button


class LabSubmissionReviewWidget(QWidget):
    def __init__(self, faculty_id: int):
        super().__init__()
        self.faculty_id = faculty_id
        self.setStyleSheet(POSITIVUS_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        layout.addWidget(create_section_header("Lab Submission Review", "Review student work before marking an experiment complete"))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Roll Number", "Student", "Course", "Experiment", "Submitted", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._show_work)
        layout.addWidget(self.table, 1)
        self.work = QTextEdit()
        self.work.setReadOnly(True)
        self.work.setPlaceholderText("Select a submission to read the student's work notes.")
        self.work.setMinimumHeight(120)
        layout.addWidget(self.work)
        actions = QHBoxLayout()
        approve = QPushButton("Approve as Complete")
        style_action_button(approve, "primary")
        approve.clicked.connect(lambda: self._review("Completed"))
        revise = QPushButton("Request Revision")
        style_action_button(revise, "outline")
        revise.clicked.connect(lambda: self._review("Needs Revision"))
        actions.addWidget(approve)
        actions.addWidget(revise)
        actions.addStretch()
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        self.rows = get_lab_submission_reviews(self.faculty_id)
        self.table.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            submission_id, roll, name, code, title, work, submitted, status = row
            for col, value in enumerate((roll, name, code, title, submitted, status)):
                self.table.setItem(index, col, QTableWidgetItem(str(value)))
        self.work.clear()

    def _show_work(self):
        row = self.table.currentRow()
        if 0 <= row < len(getattr(self, "rows", [])):
            self.work.setPlainText(self.rows[row][5])

    def _review(self, decision: str):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Lab review", "Select a submission first.")
            return
        try:
            review_lab_submission(self.rows[row][0], self.faculty_id, decision)
            self.refresh()
        except Exception as error:
            QMessageBox.critical(self, "Could not update review", str(error))
