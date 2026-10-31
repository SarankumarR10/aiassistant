"""Faculty tools for class cohorts, teaching profiles, and subject allocations."""
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView,
)

from database.database import (
    assign_subject_to_class, create_academic_class, current_academic_year,
    get_academic_classes, get_class_subjects, get_faculty_directory, get_subjects,
    update_faculty_profile,
)
from gui.theme import create_section_header, style_action_button


def _class_label(row):
    return f"{row[1]} · Year {row[2]} · Section {row[3]} · {row[4]} ({row[5]} students)"


class AcademicStructureWidget(QWidget):
    def __init__(self, faculty_id: int):
        super().__init__()
        self.faculty_id = faculty_id
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        root.addWidget(create_section_header(
            "Academic Structure", "Organize students by year and class, then assign subjects to faculty"
        ))

        class_group = QGroupBox("Create an academic class")
        class_form = QFormLayout(class_group)
        self.department = QLineEdit("CSE")
        self.class_year = QSpinBox()
        self.class_year.setRange(1, 8)
        self.class_year.setValue(1)
        self.section = QLineEdit("A")
        self.academic_year = QLineEdit(current_academic_year())
        self.create_class_button = QPushButton("Create Class")
        self.create_class_button.clicked.connect(self.create_class)
        class_form.addRow("Department / program", self.department)
        class_form.addRow("Year of study", self.class_year)
        class_form.addRow("Class section", self.section)
        class_form.addRow("Academic year", self.academic_year)
        class_form.addRow("", self.create_class_button)
        root.addWidget(class_group)

        assignment_group = QGroupBox("Assign a subject and faculty member")
        assignment_form = QFormLayout(assignment_group)
        self.class_picker = QComboBox()
        self.subject_picker = QComboBox()
        self.faculty_picker = QComboBox()
        self.term = QComboBox()
        self.term.addItems(["Full Year", "Semester 1", "Semester 2"])
        self.class_picker.currentIndexChanged.connect(self.refresh_allocations)
        self.allocate_button = QPushButton("Save Teaching Assignment")
        style_action_button(self.allocate_button, "primary")
        self.allocate_button.clicked.connect(self.assign_subject)
        assignment_form.addRow("Class", self.class_picker)
        assignment_form.addRow("Subject", self.subject_picker)
        assignment_form.addRow("Faculty", self.faculty_picker)
        assignment_form.addRow("Term", self.term)
        assignment_form.addRow("", self.allocate_button)
        root.addWidget(assignment_group)

        self.allocations_table = QTableWidget(0, 4)
        self.allocations_table.setHorizontalHeaderLabels(["Class", "Subject", "Faculty", "Term"])
        self.allocations_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.allocations_table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(QLabel("Teaching assignments"))
        root.addWidget(self.allocations_table, 1)

        profile_group = QGroupBox("My faculty profile")
        profile_form = QFormLayout(profile_group)
        self.employee_code = QLineEdit()
        self.employee_code.setPlaceholderText("Optional staff / employee ID")
        self.faculty_department = QLineEdit()
        self.faculty_department.setPlaceholderText("Department, for example CSE")
        self.designation = QLineEdit("Faculty")
        save_profile = QPushButton("Save My Profile")
        save_profile.clicked.connect(self.save_profile)
        profile_form.addRow("Employee ID", self.employee_code)
        profile_form.addRow("Department", self.faculty_department)
        profile_form.addRow("Designation", self.designation)
        profile_form.addRow("", save_profile)
        root.addWidget(profile_group)

    def refresh(self):
        try:
            self.classes = get_academic_classes(faculty_id=self.faculty_id)
            self.faculty = get_faculty_directory(self.faculty_id)
            self.class_picker.blockSignals(True)
            current_class = self.class_picker.currentData()
            self.class_picker.clear()
            for row in self.classes:
                self.class_picker.addItem(_class_label(row), row[0])
            if current_class is not None:
                index = self.class_picker.findData(current_class)
                if index >= 0:
                    self.class_picker.setCurrentIndex(index)
            self.class_picker.blockSignals(False)
            self.subject_picker.clear()
            for subject_id, code, name in get_subjects():
                self.subject_picker.addItem(f"{code} · {name}", subject_id)
            self.faculty_picker.clear()
            for faculty_id, name, employee_code, department, designation in self.faculty:
                self.faculty_picker.addItem(name, faculty_id)
                if faculty_id == self.faculty_id:
                    self.employee_code.setText(employee_code or "")
                    self.faculty_department.setText(department or "")
                    self.designation.setText(designation or "Faculty")
            self.refresh_allocations()
        except Exception as error:
            self.class_picker.blockSignals(False)
            QMessageBox.warning(self, "Could not load academic structure", str(error))

    def create_class(self):
        try:
            create_academic_class(
                self.faculty_id, self.department.text(), self.class_year.value(),
                self.section.text(), self.academic_year.text(),
            )
            self.refresh()
            QMessageBox.information(self, "Class created", "The academic class is ready for student enrollment and subject assignments.")
        except Exception as error:
            QMessageBox.warning(self, "Could not create class", str(error))

    def assign_subject(self):
        class_id = self.class_picker.currentData()
        subject_id = self.subject_picker.currentData()
        faculty_id = self.faculty_picker.currentData()
        if class_id is None or subject_id is None or faculty_id is None:
            QMessageBox.information(self, "Teaching assignment", "Choose a class, subject, and faculty member first.")
            return
        try:
            assign_subject_to_class(
                self.faculty_id, int(class_id), int(subject_id), int(faculty_id), self.term.currentText()
            )
            self.refresh_allocations()
            QMessageBox.information(self, "Assignment saved", "The subject is now linked to this class and faculty member.")
        except Exception as error:
            QMessageBox.warning(self, "Could not assign subject", str(error))

    def refresh_allocations(self, *_):
        class_id = self.class_picker.currentData()
        if class_id is None:
            self.allocations_table.setRowCount(0)
            return
        try:
            mappings = get_class_subjects(int(class_id))
            self.allocations_table.setRowCount(len(mappings))
            class_row = next((row for row in self.classes if row[0] == class_id), None)
            label = _class_label(class_row) if class_row else str(class_id)
            for index, mapping in enumerate(mappings):
                values = (label, f"{mapping[1]} · {mapping[2]}", mapping[4], mapping[5])
                for column, value in enumerate(values):
                    self.allocations_table.setItem(index, column, QTableWidgetItem(str(value)))
        except Exception as error:
            QMessageBox.warning(self, "Could not load teaching assignments", str(error))

    def save_profile(self):
        try:
            update_faculty_profile(
                self.faculty_id, self.employee_code.text(),
                self.faculty_department.text(), self.designation.text(),
            )
            QMessageBox.information(self, "Profile saved", "Your faculty profile was updated.")
            self.refresh()
        except Exception as error:
            QMessageBox.warning(self, "Could not save profile", str(error))
