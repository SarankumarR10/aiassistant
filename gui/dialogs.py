import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


DIALOG_STYLE = """
QDialog { background: #1B2028; color: #EEF3FA; font-family: 'Segoe UI'; }
QLabel { color: #EEF3FA; }
QLabel#title { font-size: 22px; font-weight: 700; }
QLabel#subtitle { color: #AAB6C8; font-size: 12px; }
QFrame#card { background: #282E38; border: 1px solid #404957; border-radius: 12px; }
QTableWidget { background: #282E38; alternate-background-color: #232833; color: #EEF3FA; gridline-color: #404957; border: 1px solid #404957; border-radius: 8px; }
QHeaderView::section { background: #202631; color: #C7D2E5; border: none; padding: 9px; font-weight: 700; }
QPushButton { background: #245FBA; color: white; border: none; border-radius: 8px; padding: 10px 14px; font-weight: 700; }
QPushButton:hover { background: #3377DC; }
QPushButton#secondary { background: #303947; border: 1px solid #4A5668; }
QPushButton#secondary:hover { background: #3C495B; }
"""


class AttendanceTakerDialog(QDialog):
    """Faculty attendance register using session-only demonstration data."""

    STUDENTS = (
        ("23CSE001", "Aadhavan R", "III CSE - A"),
        ("23CSE002", "Bhavya S", "III CSE - A"),
        ("23CSE003", "Dinesh K", "III CSE - A"),
        ("23CSE004", "Harini M", "III CSE - A"),
        ("23CSE005", "Karthik V", "III CSE - A"),
        ("23CSE006", "Nivetha P", "III CSE - A"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EduPilot - Attendance Taker")
        self.setMinimumSize(760, 510)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 25)
        layout.setSpacing(14)

        title = QLabel("Attendance Taker")
        title.setObjectName("title")
        subtitle = QLabel("III CSE - A  |  Data Structures  |  Today, 09:45 AM")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.table = QTableWidget(len(self.STUDENTS), 4)
        self.table.setHorizontalHeaderLabels(("Register No.", "Student", "Class", "Present"))
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, student in enumerate(self.STUDENTS):
            for column, value in enumerate(student):
                self.table.setItem(row, column, QTableWidgetItem(value))
            present = QCheckBox("Present")
            present.setChecked(True)
            present.setStyleSheet("color: #BFEFD9; padding-left: 16px;")
            self.table.setCellWidget(row, 3, present)
        layout.addWidget(self.table)

        footer = QHBoxLayout()
        self.summary = QLabel("6 of 6 students marked present")
        self.summary.setStyleSheet("color: #AAB6C8;")
        footer.addWidget(self.summary)
        footer.addStretch()
        save = QPushButton("Save Attendance")
        save.clicked.connect(self.save_attendance)
        footer.addWidget(save)
        layout.addLayout(footer)

    def save_attendance(self) -> None:
        present_count = sum(
            self.table.cellWidget(row, 3).isChecked() for row in range(self.table.rowCount())
        )
        self.summary.setText(f"{present_count} of {self.table.rowCount()} students marked present")
        QMessageBox.information(self, "EduPilot", "Attendance saved for this UI prototype. SQLite storage will be connected in the next phase.")


class StudentDirectoryDialog(QDialog):
    """Faculty student-management view using demonstration records."""

    RECORDS = (
        ("23CSE001", "Aadhavan R", "III CSE - A", "92%"),
        ("23CSE002", "Bhavya S", "III CSE - A", "88%"),
        ("23CSE003", "Dinesh K", "III CSE - A", "74%"),
        ("23CSE004", "Harini M", "III CSE - A", "95%"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EduPilot - Student Management")
        self.setMinimumSize(760, 480)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 25)
        title = QLabel("Student Management")
        title.setObjectName("title")
        subtitle = QLabel("Search, review, and maintain student information and attendance status.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        table = QTableWidget(len(self.RECORDS), 4)
        table.setHorizontalHeaderLabels(("Register No.", "Student", "Class", "Attendance"))
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        for row, record in enumerate(self.RECORDS):
            for column, value in enumerate(record):
                table.setItem(row, column, QTableWidgetItem(value))
        layout.addWidget(table)
        actions = QHBoxLayout()
        actions.addStretch()
        add = QPushButton("Add Student")
        add.clicked.connect(lambda: QMessageBox.information(self, "EduPilot", "Student creation will be stored in SQLite in the next phase."))
        actions.addWidget(add)
        layout.addLayout(actions)


class LabAssistantDialog(QDialog):
    """Classroom/lab assistant with tools appropriate to the selected role."""

    def __init__(self, role: str, parent=None) -> None:
        super().__init__(parent)
        self.role = role
        self.setWindowTitle("EduPilot - Lab Assistant")
        self.setMinimumSize(720, 440)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 25)
        layout.setSpacing(14)

        title = QLabel("Lab Assistant")
        title.setObjectName("title")
        subtitle = QLabel("Today's guided laboratory workspace")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        experiment = QFrame()
        experiment.setObjectName("card")
        experiment_layout = QVBoxLayout(experiment)
        experiment_name = QLabel("TODAY'S EXPERIMENT")
        experiment_name.setStyleSheet("color: #AAB6C8; font-size: 11px; font-weight: 700;")
        experiment_title = QLabel("Implement Queue using Array")
        experiment_title.setStyleSheet("font-size: 19px; font-weight: 700;")
        description = QLabel("Create enqueue and dequeue operations, test overflow/underflow, and update your record.")
        description.setWordWrap(True)
        description.setStyleSheet("color: #C5D0DE;")
        experiment_layout.addWidget(experiment_name)
        experiment_layout.addWidget(experiment_title)
        experiment_layout.addWidget(description)
        layout.addWidget(experiment)

        details = QLabel("Assigned system: 18     |     Lab: Data Structures     |     Manual: Java Lab Manual")
        details.setStyleSheet("color: #AAB6C8; padding: 4px 0;")
        layout.addWidget(details)
        buttons = QHBoxLayout()
        open_vscode = QPushButton("Open VS Code")
        open_vscode.clicked.connect(self.open_vscode)
        buttons.addWidget(open_vscode)
        manual = QPushButton("Open Lab Manual")
        manual.setObjectName("secondary")
        manual.clicked.connect(self.open_manual)
        buttons.addWidget(manual)
        if role == "faculty":
            readiness = QPushButton("View System Status")
            readiness.setObjectName("secondary")
            readiness.clicked.connect(lambda: QMessageBox.information(self, "EduPilot", "42 of 44 systems are online. Systems 07 and 31 are flagged for maintenance."))
            buttons.addWidget(readiness)
        complete = QPushButton("Mark Experiment Complete")
        complete.setObjectName("secondary")
        complete.clicked.connect(lambda: QMessageBox.information(self, "EduPilot", "Experiment completion recorded for this UI prototype."))
        buttons.addWidget(complete)
        layout.addLayout(buttons)

    def open_vscode(self) -> None:
        executable = shutil.which("code") or shutil.which("code.cmd")
        if executable is None:
            QMessageBox.information(self, "VS Code not found", "Install VS Code and add its 'code' command to PATH to launch it from EduPilot.")
            return
        subprocess.Popen([executable, str(Path.cwd())])

    def open_manual(self) -> None:
        QMessageBox.information(self, "Lab Manual", "Add approved laboratory PDFs to the project knowledge base. EduPilot will then open the selected manual here.")
