from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView,
)

from database.database import (
    get_all_academic_records, get_student_academic_records,
    save_academic_record,
)
from gui.theme import POSITIVUS_QSS, create_section_header


class AcademicTrackerWidget(QWidget):
    """Faculty mark entry and a read-only personal academic record for students."""

    def __init__(self, user, role: str):
        super().__init__()
        self.user = user
        self.role = role
        self.setStyleSheet(POSITIVUS_QSS)
        self._build_ui()
        self.load_records()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        subtitle = (
            "Review and update marks by student and subject. Each component is out of 100."
            if self.role == "faculty"
            else "Review marks published for your subjects. Each component is out of 100."
        )
        layout.addWidget(create_section_header("Academic Records", subtitle))

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        if self.role == "faculty":
            self.table.setColumnCount(7)
            self.table.setHorizontalHeaderLabels(
                ["Roll Number", "Student", "Subject", "Internal / 100", "Assignment / 100", "Lab / 100", "Total / 300"]
            )
            self.table.itemSelectionChanged.connect(self._select_record)
        else:
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(
                ["Subject", "Internal / 100", "Assignment / 100", "Lab / 100", "Total / 300"]
            )
        layout.addWidget(self.table, 1)

        if self.role == "faculty":
            panel = QFrame()
            panel.setObjectName("surfaceCard")
            panel.setStyleSheet(
                "QFrame#surfaceCard { background: #FFFFFF; border: 1px solid #DCE2E7; "
                "border-radius: 9px; padding: 14px; }"
            )
            row = QHBoxLayout(panel)
            self.selected_label = QLabel("Select a student and subject above to enter marks.")
            self.selected_label.setMinimumWidth(200)
            row.addWidget(self.selected_label, 1)
            self.mark_inputs = []
            for name in ("Internal", "Assignment", "Lab"):
                field = QDoubleSpinBox()
                field.setRange(0, 100)
                field.setDecimals(1)
                field.setPrefix(f"{name}: ")
                field.setEnabled(False)
                row.addWidget(field)
                self.mark_inputs.append(field)
            self.save_button = QPushButton("Save Marks")
            self.save_button.setProperty("class", "secondary")
            self.save_button.setEnabled(False)
            self.save_button.clicked.connect(self._save)
            row.addWidget(self.save_button)
            layout.addWidget(panel)

    def load_records(self):
        self.table.setRowCount(0)
        if self.role == "faculty":
            rows = get_all_academic_records()
            for row, record in enumerate(rows):
                student_id, roll, student, subject_id, code, subject, internal, assignment, lab, total = record
                self.table.insertRow(row)
                values = (roll, student, f"{code} — {subject}", internal, assignment, lab, total)
                for col, value in enumerate(values):
                    item = QTableWidgetItem("" if value is None else str(value))
                    if col == 0:
                        item.setData(Qt.UserRole, student_id)
                        item.setData(Qt.UserRole + 1, subject_id)
                    self.table.setItem(row, col, item)
        else:
            rows = get_student_academic_records(self.user[0])
            for row, record in enumerate(rows):
                self.table.insertRow(row)
                values = (f"{record[0]} — {record[1]}", *record[2:])
                for col, value in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem("—" if value is None else str(value)))
            if not rows:
                self.table.setRowCount(1)
                self.table.setSpan(0, 0, 1, 5)
                self.table.setItem(0, 0, QTableWidgetItem("No academic marks have been published yet."))

    def _select_record(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            return
        self.selected_student_id = self.table.item(row, 0).data(Qt.UserRole)
        self.selected_subject_id = self.table.item(row, 0).data(Qt.UserRole + 1)
        self.selected_label.setText(
            f"{self.table.item(row, 1).text()} · {self.table.item(row, 2).text()}"
        )
        for index, column in enumerate((3, 4, 5)):
            value = self.table.item(row, column).text()
            self.mark_inputs[index].setValue(float(value) if value else 0)
            self.mark_inputs[index].setEnabled(True)
        self.save_button.setEnabled(True)

    def _save(self):
        if not getattr(self, "selected_student_id", None):
            QMessageBox.information(self, "Academic Records", "Select a student record first.")
            return
        try:
            save_academic_record(
                self.selected_student_id,
                self.selected_subject_id,
                *(field.value() for field in self.mark_inputs),
                faculty_id=self.user[0],
            )
            self.load_records()
            self.selected_label.setText("Marks saved. Select another student and subject to continue.")
            self.save_button.setEnabled(False)
            for field in self.mark_inputs:
                field.setEnabled(False)
        except Exception as exc:
            QMessageBox.critical(self, "Could not save marks", str(exc))
