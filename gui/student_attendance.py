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

from database.database import (
    get_student_profile,
    get_student_attendance,
    get_student_attendance_history
)


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

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        self.setStyleSheet("""
            QWidget {
                background-color: #111827;
                color: white;
            }

            QLabel {
                color: white;
            }

            QTableWidget {
                background-color: #1F2937;
                color: white;
                border: 1px solid #334155;
                border-radius: 8px;
                gridline-color: #334155;
            }

            QHeaderView::section {
                background-color: #172033;
                color: white;
                padding: 10px;
                border: none;
                font-weight: bold;
            }

            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
            }

            QPushButton:hover {
                background-color: #3B82F6;
            }
        """)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            30,
            25,
            30,
            25
        )

        # ====================================================
        # HEADER
        # ====================================================

        title = QLabel(
            "My Attendance"
        )

        title.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
        """)

        layout.addWidget(title)

        subtitle = QLabel(
            "View your attendance percentage "
            "and complete attendance history"
        )

        subtitle.setStyleSheet("""
            color: #94A3B8;
            font-size: 14px;
        """)

        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # ====================================================
        # STUDENT INFORMATION
        # ====================================================

        self.student_info = QLabel(
            "Loading student profile..."
        )

        self.student_info.setStyleSheet("""
            background-color: #1F2937;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 15px;
            color: #CBD5E1;
            font-size: 14px;
        """)

        layout.addWidget(
            self.student_info
        )

        layout.addSpacing(15)

        # ====================================================
        # SUMMARY CARDS
        # ====================================================

        summary_layout = QHBoxLayout()

        self.overall_card = self.create_summary_card(
            "Overall Attendance",
            "--",
            "#60A5FA"
        )

        self.present_card = self.create_summary_card(
            "Present",
            "0",
            "#86EFAC"
        )

        self.classes_card = self.create_summary_card(
            "Total Classes",
            "0",
            "#CBD5E1"
        )

        self.absent_card = self.create_summary_card(
            "Absent",
            "0",
            "#FCA5A5"
        )

        summary_layout.addWidget(
            self.overall_card
        )

        summary_layout.addWidget(
            self.present_card
        )

        summary_layout.addWidget(
            self.classes_card
        )

        summary_layout.addWidget(
            self.absent_card
        )

        layout.addLayout(
            summary_layout
        )

        layout.addSpacing(20)

        # ====================================================
        # SUBJECT-WISE ATTENDANCE
        # ====================================================

        subject_title = QLabel(
            "Subject-wise Attendance"
        )

        subject_title.setStyleSheet("""
            font-size: 19px;
            font-weight: bold;
        """)

        layout.addWidget(
            subject_title
        )

        layout.addSpacing(10)

        self.subject_table = QTableWidget()

        self.subject_table.setColumnCount(5)

        self.subject_table.setHorizontalHeaderLabels([
            "Code",
            "Subject",
            "Classes",
            "Present",
            "Attendance %"
        ])

        self.subject_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.subject_table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.subject_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        layout.addWidget(
            self.subject_table
        )

        layout.addSpacing(20)

        # ====================================================
        # HISTORY
        # ====================================================

        history_title = QLabel(
            "Attendance History"
        )

        history_title.setStyleSheet("""
            font-size: 19px;
            font-weight: bold;
        """)

        layout.addWidget(
            history_title
        )

        self.history_table = QTableWidget()

        self.history_table.setColumnCount(4)

        self.history_table.setHorizontalHeaderLabels([
            "Date",
            "Code",
            "Subject",
            "Status"
        ])

        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.history_table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        layout.addWidget(
            self.history_table
        )

        # ====================================================
        # REFRESH
        # ====================================================

        refresh_button = QPushButton(
            "↻  Refresh Attendance"
        )

        refresh_button.clicked.connect(
            self.load_attendance
        )

        layout.addWidget(
            refresh_button
        )

    # ========================================================
    # SUMMARY CARD
    # ========================================================

    def create_summary_card(
        self,
        title,
        value,
        text_color
    ):

        card = QFrame()

        card.setMinimumHeight(100)

        card.setStyleSheet("""
            QFrame {
                background-color: #1F2937;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)

        card_layout = QVBoxLayout(card)

        title_label = QLabel(title)

        title_label.setStyleSheet("""
            color: #94A3B8;
            font-size: 13px;
        """)

        value_label = QLabel(value)

        value_label.setStyleSheet(f"""
            color: {text_color};
            font-size: 25px;
            font-weight: bold;
        """)

        card_layout.addWidget(
            title_label
        )

        card_layout.addWidget(
            value_label
        )

        # Store label so we can update it later
        card.value_label = value_label

        return card

    # ========================================================
    # LOAD ATTENDANCE
    # ========================================================

    def load_attendance(self):

        profile = get_student_profile(
            self.user_id
        )

        if profile is None:

            self.student_info.setText(
                "Student profile not found."
            )

            QMessageBox.warning(
                self,
                "EduPilot",
                "No student profile is linked "
                "to this login account."
            )

            return

        student_id = profile[0]
        roll_number = profile[2]
        name = profile[3]
        department = profile[4]
        year = profile[5]
        section = profile[6]

        self.student_info.setText(
            f"Student: {name}    |    "
            f"Roll No: {roll_number}    |    "
            f"Department: {department}    |    "
            f"Year: {year}    |    "
            f"Section: {section}"
        )

        self.load_subject_summary()

        self.load_history()

    # ========================================================
    # SUBJECT SUMMARY
    # ========================================================

    def load_subject_summary(self):

        rows = get_student_attendance(
            self.user_id
        )

        self.subject_table.setRowCount(
            len(rows)
        )

        total_classes = 0
        total_present = 0

        for row, data in enumerate(rows):

            code = data[0]
            subject = data[1]
            classes = data[2]
            present = data[3]

            if classes > 0:

                percentage = (
                    present / classes
                ) * 100

            else:

                percentage = 0

            total_classes += classes
            total_present += present

            values = [
                code,
                subject,
                str(classes),
                str(present),
                (
                    f"{percentage:.1f}%"
                    if classes > 0
                    else "-"
                )
            ]

            for column, value in enumerate(values):

                self.subject_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value)
                )

        absent = (
            total_classes -
            total_present
        )

        if total_classes > 0:

            overall = (
                total_present /
                total_classes
            ) * 100

        else:

            overall = 0

        self.overall_card.value_label.setText(
            f"{overall:.1f}%"
        )

        self.present_card.value_label.setText(
            str(total_present)
        )

        self.classes_card.value_label.setText(
            str(total_classes)
        )

        self.absent_card.value_label.setText(
            str(absent)
        )

    # ========================================================
    # ATTENDANCE HISTORY
    # ========================================================

    def load_history(self):

        rows = get_student_attendance_history(
            self.user_id
        )

        self.history_table.setRowCount(
            len(rows)
        )

        for row, data in enumerate(rows):

            attendance_date = data[0]
            code = data[1]
            subject = data[2]
            status = data[3]

            values = [
                attendance_date,
                code,
                subject,
                status
            ]

            for column, value in enumerate(values):

                item = QTableWidgetItem(
                    str(value)
                )

                self.history_table.setItem(
                    row,
                    column,
                    item
                )