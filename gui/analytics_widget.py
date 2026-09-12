from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QProgressBar
)
from PySide6.QtCore import Qt
from database.database import get_attendance_analytics, get_students

class ClassroomAnalyticsWidget(QWidget):
    """
    Classroom Analytics Dashboard Widget.
    Displays overall attendance %, most absent students, lab health, and FAQ activity.
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Classroom & Academic Analytics")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)

        # KPI Summary Cards
        kpi_layout = QHBoxLayout()
        
        card1 = self._create_kpi_card("Class Average Attendance", "84.2%", "#2ecc71")
        card2 = self._create_kpi_card("Most Absent Count (<75%)", "1 Student", "#e74c3c")
        card3 = self._create_kpi_card("Active Lab Usage", "92%", "#3498db")
        card4 = self._create_kpi_card("Top Asked Topic", "JVM & Unit 3", "#f39c12")

        kpi_layout.addWidget(card1)
        kpi_layout.addWidget(card2)
        kpi_layout.addWidget(card3)
        kpi_layout.addWidget(card4)

        layout.addLayout(kpi_layout)

        # Student Attendance Table
        table_title = QLabel("Student Attendance & Performance Ranking")
        table_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #3498db; margin-top: 10px;")
        layout.addWidget(table_title)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Roll Number", "Student Name", "Total Sessions", "Present", "Attendance %"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e2f;
                color: #FFFFFF;
                gridline-color: #2e2e42;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #2a2a3d;
                color: #3498db;
                font-weight: bold;
                padding: 6px;
            }
        """)
        layout.addWidget(self.table)

        self.load_analytics_data()

    def _create_kpi_card(self, label: str, value: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #1e1e2f;
                border-left: 5px solid {color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        v = QVBoxLayout(frame)
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
        title_lbl = QLabel(label)
        title_lbl.setStyleSheet("font-size: 12px; color: #aaaaaa;")
        v.addWidget(val_lbl)
        v.addWidget(title_lbl)
        return frame

    def load_analytics_data(self):
        rows = get_attendance_analytics()
        self.table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            roll, name, total, present, pct = row
            self.table.setItem(idx, 0, QTableWidgetItem(str(roll)))
            self.table.setItem(idx, 1, QTableWidgetItem(str(name)))
            self.table.setItem(idx, 2, QTableWidgetItem(str(total)))
            self.table.setItem(idx, 3, QTableWidgetItem(str(present)))

            pct_item = QTableWidgetItem(f"{pct}%")
            if pct < 75:
                pct_item.setForeground(Qt.red)
            else:
                pct_item.setForeground(Qt.green)
            self.table.setItem(idx, 4, pct_item)
