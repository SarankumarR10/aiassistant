from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QComboBox, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QHeaderView,
)

from database.database import (
    create_lab_experiment, get_academic_classes, get_lab_experiment_progress,
    get_lab_experiments, get_subjects, review_lab_submission,
)
from ai.rag_engine import rag_engine
from gui.theme import create_section_header, style_action_button
from storage.local_storage import storage_service


class LabManualsWidget(QWidget):
    """Faculty lab manual publishing and class-scoped student progress review."""

    def __init__(self, faculty_id: int):
        super().__init__()
        self.faculty_id = faculty_id
        self.experiments = []
        self.progress = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        root.addWidget(create_section_header(
            "Lab Manuals & Experiment Progress",
            "Publish class experiments, attach reference manuals, and review student work.",
        ))

        form_box = QGroupBox("Publish a lab experiment")
        form = QFormLayout(form_box)
        self.class_picker = QComboBox()
        self.classes = get_academic_classes(faculty_id=self.faculty_id)
        self.class_labels = {}
        for row in self.classes:
            label = f"{row[1]} · Year {row[2]} · Section {row[3]} · {row[4]}"
            self.class_labels[row[0]] = label
            self.class_picker.addItem(label, row[0])
        self.class_picker.currentIndexChanged.connect(self._load_subjects)

        self.subject_picker = QComboBox()
        self.experiment_number = QSpinBox()
        self.experiment_number.setRange(1, 1000)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("For example: Implement a binary search tree")
        self.manual_path = QLineEdit()
        self.manual_path.setReadOnly(True)
        self.manual_path.setPlaceholderText("Optional PDF, TXT, or Markdown reference manual")
        browse = QPushButton("Choose Manual")
        browse.clicked.connect(self._browse_manual)
        manual_row = QHBoxLayout()
        manual_row.addWidget(self.manual_path, 1)
        manual_row.addWidget(browse)
        self.instructions = QTextEdit()
        self.instructions.setPlaceholderText("Write the experiment objective, steps, and expected output.")
        self.instructions.setMinimumHeight(90)
        publish = QPushButton("Publish Experiment")
        style_action_button(publish, "primary")
        publish.clicked.connect(self._publish)
        form.addRow("Class", self.class_picker)
        form.addRow("Subject", self.subject_picker)
        form.addRow("Experiment number", self.experiment_number)
        form.addRow("Title", self.title_input)
        form.addRow("Reference manual", manual_row)
        form.addRow("Instructions", self.instructions)
        form.addRow("", publish)
        root.addWidget(form_box)

        self.experiment_table = QTableWidget(0, 5)
        self.experiment_table.setHorizontalHeaderLabels(["Subject", "Class", "Experiment", "Title", "Manual"])
        self.experiment_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.experiment_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.experiment_table.setSelectionMode(QTableWidget.SingleSelection)
        self.experiment_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.experiment_table.itemSelectionChanged.connect(self._load_progress)
        root.addWidget(QLabel("Published experiments"))
        root.addWidget(self.experiment_table, 1)

        actions = QHBoxLayout()
        self.open_manual_button = QPushButton("Open Selected Manual")
        self.open_manual_button.setEnabled(False)
        self.open_manual_button.clicked.connect(self._open_manual)
        self.approve_button = QPushButton("Mark Selected Work Complete")
        self.approve_button.setEnabled(False)
        self.approve_button.clicked.connect(lambda: self._review("Completed"))
        self.revision_button = QPushButton("Request Revision")
        self.revision_button.setProperty("class", "outline")
        self.revision_button.setEnabled(False)
        self.revision_button.clicked.connect(lambda: self._review("Needs Revision"))
        actions.addWidget(self.open_manual_button)
        actions.addStretch()
        actions.addWidget(self.approve_button)
        actions.addWidget(self.revision_button)
        root.addLayout(actions)

        splitter = QSplitter(Qt.Vertical)
        self.progress_table = QTableWidget(0, 4)
        self.progress_table.setHorizontalHeaderLabels(["Roll Number", "Student", "Progress", "Last Submitted"])
        self.progress_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.progress_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.progress_table.setSelectionMode(QTableWidget.SingleSelection)
        self.progress_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.progress_table.itemSelectionChanged.connect(self._show_submission)
        self.submission_detail = QTextEdit()
        self.submission_detail.setReadOnly(True)
        self.submission_detail.setPlaceholderText("Select a student to view their submitted experiment work.")
        splitter.addWidget(self.progress_table)
        splitter.addWidget(self.submission_detail)
        root.addWidget(QLabel("Student progress and submitted work"))
        root.addWidget(splitter, 1)
        self._load_subjects()

    def _load_subjects(self, *_):
        self.subject_picker.clear()
        class_id = self.class_picker.currentData()
        if class_id is None:
            return
        for subject in get_subjects(faculty_id=self.faculty_id, class_id=int(class_id)):
            self.subject_picker.addItem(f"{subject[1]} — {subject[2]}", subject[0])

    def _browse_manual(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a Lab Reference Manual", "",
            "Lab manuals (*.pdf *.txt *.md)",
        )
        if path:
            self.manual_path.setText(path)

    def _publish(self):
        manual_file = self.manual_path.text().strip() or None
        title = self.title_input.text().strip()
        subject_id = self.subject_picker.currentData()
        class_id = self.class_picker.currentData()
        unit_number = self.experiment_number.value()
        try:
            experiment_id = create_lab_experiment(
                self.faculty_id, int(class_id), int(subject_id), unit_number,
                title, self.instructions.toPlainText(), manual_file,
            )
            self.title_input.clear()
            self.instructions.clear()
            self.manual_path.clear()
            self.refresh()
            for row, experiment in enumerate(self.experiments):
                if experiment[0] == experiment_id:
                    self.experiment_table.selectRow(row)
                    break
            index_error = None
            if manual_file:
                try:
                    rag_engine.ingest_file(
                        title=f"Lab Manual — Experiment {unit_number}: {title}",
                        file_path=manual_file, subject_id=int(subject_id),
                        uploaded_by=self.faculty_id, unit_number=min(unit_number, 20),
                        class_id=int(class_id),
                    )
                except Exception as error:
                    index_error = error
            if index_error:
                QMessageBox.warning(
                    self, "Experiment published; AI indexing needs attention",
                    "Students can view the experiment and open its manual, but the AI tutor could not index the manual.\n\n"
                    f"Details: {index_error}",
                )
            else:
                QMessageBox.information(
                    self, "Experiment published",
                    "Students in the selected class can now view the experiment and reference manual.",
                )
        except Exception as error:
            QMessageBox.warning(self, "Could not publish experiment", str(error))

    def refresh(self):
        self.experiments = get_lab_experiments(faculty_id=self.faculty_id)
        self.experiment_table.setRowCount(len(self.experiments))
        for index, item in enumerate(self.experiments):
            manual = storage_service.file_name(item[6]) if item[6] else "—"
            values = (f"{item[1]} — {item[2]}", self.class_labels.get(item[7], "All classes"),
                      f"Experiment {item[3]}", item[4], manual)
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.UserRole, item[0])
                self.experiment_table.setItem(index, column, cell)
        self.progress_table.setRowCount(0)
        self.submission_detail.clear()
        self.open_manual_button.setEnabled(False)
        self.approve_button.setEnabled(False)
        self.revision_button.setEnabled(False)

    def _selected_experiment(self):
        row = self.experiment_table.currentRow()
        return self.experiments[row] if 0 <= row < len(self.experiments) else None

    def _load_progress(self):
        experiment = self._selected_experiment()
        if not experiment:
            return
        self.open_manual_button.setEnabled(bool(experiment[6]))
        try:
            self.progress = get_lab_experiment_progress(experiment[0], self.faculty_id)
        except Exception as error:
            QMessageBox.warning(self, "Could not load experiment progress", str(error))
            self.progress = []
        self.progress_table.setRowCount(len(self.progress))
        for row, entry in enumerate(self.progress):
            # entry: student id, roll, name, status, submission, submitted at, submission id
            values = (entry[1], entry[2], entry[3], entry[5] or "—")
            for column, value in enumerate(values):
                self.progress_table.setItem(row, column, QTableWidgetItem(str(value)))
        self.submission_detail.clear()
        self.approve_button.setEnabled(False)
        self.revision_button.setEnabled(False)

    def _show_submission(self):
        row = self.progress_table.currentRow()
        if not 0 <= row < len(self.progress):
            return
        entry = self.progress[row]
        self.submission_detail.setPlainText(entry[4] or "No work has been submitted by this student yet.")
        can_review = bool(entry[6]) and entry[3] in ("Submitted for Review", "Needs Revision")
        self.approve_button.setEnabled(can_review)
        self.revision_button.setEnabled(can_review)

    def _review(self, decision: str):
        row = self.progress_table.currentRow()
        if not 0 <= row < len(self.progress) or not self.progress[row][6]:
            return
        try:
            review_lab_submission(self.progress[row][6], self.faculty_id, decision)
            self._load_progress()
        except Exception as error:
            QMessageBox.warning(self, "Could not update lab progress", str(error))

    def _open_manual(self):
        experiment = self._selected_experiment()
        if not experiment or not experiment[6]:
            return
        path = storage_service.resolve(experiment[6])
        if not path.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve()))):
            QMessageBox.warning(self, "Manual unavailable", "The lab manual could not be opened on this device.")
