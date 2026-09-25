from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from database.database import get_attendance_analytics, get_classroom_activity_stats
from gui.theme import POSITIVUS_QSS, create_section_header


class ClassroomAnalyticsWidget(QWidget):
    """Attendance, learning-query, lab-work, and daily activity analytics."""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        layout.addWidget(create_section_header("Classroom & Academic Analytics"))
        kpis = QGridLayout()
        kpis.setHorizontalSpacing(12)
        kpis.setVerticalSpacing(12)
        self.kpis = []
        for index, title in enumerate((
            "Class Average Attendance", "Below 75%", "Students Tracked",
            "Learning Queries Today", "Lab Work Submitted Today", "Attendance Registers Today",
        )):
            card = QFrame()
            card.setObjectName("dashboardMetricCard")
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 12, 16, 12)
            box.setSpacing(4)
            value = QLabel("—")
            value.setStyleSheet("font-size: 24px; font-weight: 700; color: #26323B;")
            caption = QLabel(title)
            caption.setWordWrap(True)
            caption.setStyleSheet("font-size: 12px; color: #687782;")
            box.addWidget(value)
            box.addWidget(caption)
            self.kpis.append(value)
            kpis.addWidget(card, index // 3, index % 3)
        for column in range(3):
            kpis.setColumnStretch(column, 1)
        layout.addLayout(kpis)
        self.activity_summary = QLabel()
        self.activity_summary.setWordWrap(True)
        self.activity_summary.setStyleSheet("color: #687782; font-size: 12px;")
        layout.addWidget(self.activity_summary)
        layout.addWidget(QLabel("Student Attendance"))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Roll Number", "Student Name", "Sessions", "Present", "Absent", "Attendance"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        self.load_analytics_data()

    def load_analytics_data(self):
        rows = get_attendance_analytics()
        activity = get_classroom_activity_stats()
        measured = [row[4] for row in rows if row[2] > 0]
        values = [f"{sum(measured) / len(measured):.1f}%" if measured else "—",
                  str(sum(pct < 75 for pct in measured)) if measured else "—",
                  str(len(rows)), str(activity["learning_queries_today"]),
                  str(activity["lab_submissions_today"]), str(activity["attendance_sessions_today"])]
        for label, value in zip(self.kpis, values):
            label.setText(value)
        self.activity_summary.setText(
            "Today's activity: "
            f"{activity['assignment_submissions_today']} assignment submissions · "
            f"{activity['schedule_queries_today']} schedule queries · "
            f"{activity['exam_queries_today']} exam queries"
        )
        self.table.setRowCount(len(rows))
        for idx, (roll, name, total, present, pct) in enumerate(rows):
            values = (roll, name, total, present, max(0, total - present), f"{pct}%" if total else "—")
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 5 and total:
                    item.setForeground(QColor("#7A6B52" if pct < 75 else "#48677D"))
                self.table.setItem(idx, col, item)
