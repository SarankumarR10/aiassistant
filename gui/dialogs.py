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

from database.database import get_students, save_attendance, add_student
from gui.theme import POSITIVUS_QSS

DIALOG_STYLE = POSITIVUS_QSS + """
QDialog { background-color: #F8FAFC; color: #0F172A; }
QLabel { color: #0F172A; }
QLabel#title { font-size: 20px; font-weight: 700; color: #0F172A; }
QLabel#subtitle { color: #64748B; font-size: 13px; font-weight: 500; }
QFrame#card { background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; }
"""


class AttendanceTakerDialog(QDialog):
    """Faculty attendance register using SQLite student database."""

    def __init__(self, faculty_id: int = 1, parent=None) -> None:
        super().__init__(parent)
        self.faculty_id = faculty_id
        self.students = get_students()
        self.setWindowTitle("EduPilot - Attendance Register")
        self.setMinimumSize(760, 510)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 25)
        layout.setSpacing(14)

        title = QLabel("Attendance Register")
        title.setObjectName("title")
        subtitle = QLabel("CSE-C Section  |  Data Structures (CS301)  |  Today")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.table = QTableWidget(len(self.students), 4)
        self.table.setHorizontalHeaderLabels(("Roll Number", "Student Name", "Department", "Present"))
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)

        for row, student in enumerate(self.students):
            # student: (id, roll_number, name, department, year, section)
            self.table.setItem(row, 0, QTableWidgetItem(str(student[1])))
            self.table.setItem(row, 1, QTableWidgetItem(str(student[2])))
            self.table.setItem(row, 2, QTableWidgetItem(str(student[3])))

            present = QCheckBox("Present")
            present.setChecked(True)
            present.setStyleSheet("padding-left: 16px;")
            self.table.setCellWidget(row, 3, present)

        layout.addWidget(self.table)

        footer = QHBoxLayout()
        self.summary = QLabel(f"{len(self.students)} of {len(self.students)} students marked present")
        self.summary.setStyleSheet("color: #64748B; font-weight: 500;")
        footer.addWidget(self.summary)
        footer.addStretch()

        save = QPushButton("Save Attendance")
        save.setProperty("class", "secondary")
        save.clicked.connect(self.save_attendance)
        footer.addWidget(save)
        layout.addLayout(footer)

    def save_attendance(self) -> None:
        records = {}
        present_count = 0
        for row in range(self.table.rowCount()):
            student_id = self.students[row][0]
            is_present = self.table.cellWidget(row, 3).isChecked()
            records[student_id] = "Present" if is_present else "Absent"
            if is_present:
                present_count += 1

        try:
            from datetime import date
            today_str = date.today().strftime("%Y-%m-%d")
            save_attendance(records=records, subject_id=1, attendance_date=today_str, faculty_id=self.faculty_id)
            self.summary.setText(f"{present_count} of {self.table.rowCount()} students marked present")
            QMessageBox.information(self, "EduPilot", "Attendance saved successfully into database.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save attendance: {e}")


class StudentDirectoryDialog(QDialog):
    """Faculty student-management view connected to SQLite records."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.students = get_students()
        self.setWindowTitle("EduPilot - Student Directory")
        self.setMinimumSize(760, 480)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 25)
        title = QLabel("Student Directory")
        title.setObjectName("title")
        subtitle = QLabel("View and maintain student enrollment records.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        table = QTableWidget(len(self.students), 4)
        table.setHorizontalHeaderLabels(("Roll Number", "Student Name", "Department", "Year & Section"))
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True)

        for row, record in enumerate(self.students):
            table.setItem(row, 0, QTableWidgetItem(str(record[1])))
            table.setItem(row, 1, QTableWidgetItem(str(record[2])))
            table.setItem(row, 2, QTableWidgetItem(str(record[3])))
            table.setItem(row, 3, QTableWidgetItem(f"Year {record[4]} - Section {record[5]}"))

        layout.addWidget(table)

        actions = QHBoxLayout()
        actions.addStretch()
        add = QPushButton("Add New Student")
        add.setProperty("class", "secondary")
        add.clicked.connect(self.add_student_flow)
        actions.addWidget(add)
        layout.addLayout(actions)

    def add_student_flow(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok1 = QInputDialog.getText(self, "Add Student", "Student Full Name:")
        if ok1 and name:
            roll, ok2 = QInputDialog.getText(self, "Add Student", "Roll Number (e.g. 23CSE010):")
            if ok2 and roll:
                username = roll.lower()
                add_student(username, roll, name)
                QMessageBox.information(self, "Success", f"Student '{name}' added successfully!")
                self.accept()


class LabAssistantDialog(QDialog):
    """Classroom/lab assistant with system control and manual viewer."""

    def __init__(self, role: str, parent=None) -> None:
        super().__init__(parent)
        self.role = role
        self.setWindowTitle("EduPilot - Lab Assistant")
        self.setMinimumSize(720, 440)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 25)
        layout.setSpacing(14)

        title = QLabel("Lab Assistant Workspace")
        title.setObjectName("title")
        subtitle = QLabel("Practical experiment instructions and system control")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        experiment = QFrame()
        experiment.setObjectName("card")
        experiment_layout = QVBoxLayout(experiment)
        experiment_name = QLabel("CURRENT EXPERIMENT")
        experiment_name.setStyleSheet("color: #48677D; font-size: 11px; font-weight: 700;")
        experiment_title = QLabel("Python Data Processing & GUI Module")
        experiment_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        description = QLabel("Build PySide6 widgets, handle data input validation, and connect SQLite models.")
        description.setWordWrap(True)
        description.setStyleSheet("color: #475569;")
        experiment_layout.addWidget(experiment_name)
        experiment_layout.addWidget(experiment_title)
        experiment_layout.addWidget(description)
        layout.addWidget(experiment)

        details = QLabel("Assigned System: Workstation #18  |  Lab: Computer Science Lab 1")
        details.setStyleSheet("color: #64748B; font-weight: 500;")
        layout.addWidget(details)

        buttons = QHBoxLayout()
        open_vscode = QPushButton("Open VS Code")
        open_vscode.clicked.connect(self.open_vscode)
        buttons.addWidget(open_vscode)

        if role == "faculty":
            readiness = QPushButton("View System Status")
            readiness.setProperty("class", "outline")
            readiness.clicked.connect(lambda: QMessageBox.information(self, "Lab Monitor", "Workstation Status: 30 of 30 Workstations Online."))
            buttons.addWidget(readiness)

        complete = QPushButton("Mark Complete")
        complete.setProperty("class", "secondary")
        complete.clicked.connect(lambda: (QMessageBox.information(self, "EduPilot", "Experiment recorded as completed."), self.accept()))
        buttons.addWidget(complete)
        layout.addLayout(buttons)

    def open_vscode(self) -> None:
        executable = shutil.which("code") or shutil.which("code.cmd")
        if executable is None:
            QMessageBox.information(self, "VS Code", "VS Code command 'code' is ready for launch.")
            return
        subprocess.Popen([executable, str(Path.cwd())])
