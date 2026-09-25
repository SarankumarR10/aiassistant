from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QFrame,
    QMessageBox
)
from PySide6.QtCore import Qt

from database.database import (
    get_student_profile,
    get_student_attendance,
    get_student_attendance_history
)
from gui.theme import POSITIVUS_QSS, create_section_header


class StudentAttendanceWindow(QWidget):

    def __init__(self, user_id):
        super().__init__()

        self.user_id = user_id

        self.setWindowTitle(
            "EduPilot - My Attendance"
        )

        self.resize(1050, 750)

        self.build_ui()
        self.load_attendance()

    def build_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            28,
            24,
            28,
            24
        )

        header = create_section_header("My Attendance Percentages", "Track subject-wise class attendance and history")
        layout.addWidget(header)
        layout.addSpacing(16)

        # PROFILE SUMMARY FRAME
        self.profile_frame = QFrame()
        self.profile_frame.setObjectName("surfaceCard")
        self.profile_frame.setStyleSheet("""
            QFrame#surfaceCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 16px;
            }
            QLabel {
                color: #0F172A;
                font-weight: 500;
            }
        """)

        pf_layout = QHBoxLayout(self.profile_frame)
        self.lbl_profile_name = QLabel("Student: Loading...")
        self.lbl_profile_name.setStyleSheet("font-weight: 700; font-size: 14px; color: #0F172A;")
        self.lbl_profile_dept = QLabel("Department: --")
        self.lbl_profile_year = QLabel("Year/Section: --")

        pf_layout.addWidget(self.lbl_profile_name)
        pf_layout.addStretch()
        pf_layout.addWidget(self.lbl_profile_dept)
        pf_layout.addSpacing(20)
        pf_layout.addWidget(self.lbl_profile_year)

        layout.addWidget(self.profile_frame)
        layout.addSpacing(16)

        # TABLE
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Subject Code",
            "Subject Name",
            "Total Sessions",
            "Present Count",
            "Attendance %"
        ])

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.table)

    def load_attendance(self):
        profile = get_student_profile(self.user_id)
        if profile:
            self.lbl_profile_name.setText(f"Student: {profile[3]} ({profile[2]})")
            self.lbl_profile_dept.setText(f"Department: {profile[4]}")
            self.lbl_profile_year.setText(f"Year: {profile[5]}  |  Section: {profile[6]}")

        attendance_summary = get_student_attendance(self.user_id)
        self.table.setRowCount(len(attendance_summary))

        for row, (code, name, total, present) in enumerate(attendance_summary):
            pct = round((present / total * 100), 1) if total > 0 else None

            self.table.setItem(row, 0, QTableWidgetItem(str(code)))
            self.table.setItem(row, 1, QTableWidgetItem(str(name)))
            self.table.setItem(row, 2, QTableWidgetItem(str(total)))
            self.table.setItem(row, 3, QTableWidgetItem(str(present)))

            pct_item = QTableWidgetItem(f"{pct}%" if pct is not None else "No sessions recorded")
            self.table.setItem(row, 4, pct_item)
