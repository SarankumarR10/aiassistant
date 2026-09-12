from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QFrame, QSplitter
)
from PySide6.QtCore import Qt
from database.database import (
    get_subjects,
    get_assignments,
    add_assignment,
    get_assignment_submissions,
    submit_assignment,
    grade_submission
)

class AssignmentsWidget(QWidget):
    """
    Assignments & Submissions Management Widget supporting Faculty creation/grading and Student submissions.
    """
    def __init__(self, user, role: str = "faculty"):
        super().__init__()
        self.user = user
        self.role = role
        self.subjects = get_subjects()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title
        title_text = "Assignment Workspace & Grading Panel" if self.role == "faculty" else "My Academic Assignments & Submissions"
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        main_layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)

        # Left Column: Assignments List & Form
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)

        list_lbl = QLabel("Course Assignments List")
        list_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #60A5FA;")
        left_layout.addWidget(list_lbl)

        self.table_assignments = QTableWidget()
        self.table_assignments.setColumnCount(4)
        self.table_assignments.setHorizontalHeaderLabels(["ID", "Subject", "Assignment Title", "Due Date"])
        self.table_assignments.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_assignments.setStyleSheet("""
            QTableWidget { background-color: #1F2937; color: white; gridline-color: #374151; font-size: 13px; }
            QHeaderView::section { background-color: #111827; color: #60A5FA; font-weight: bold; }
        """)
        self.table_assignments.itemSelectionChanged.connect(self._on_assignment_selected)
        left_layout.addWidget(self.table_assignments)

        if self.role == "faculty":
            # Faculty form to create assignment
            form_lbl = QLabel("Create New Assignment")
            form_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #34D399; margin-top: 10px;")
            left_layout.addWidget(form_lbl)

            self.combo_subject = QComboBox()
            for s in self.subjects:
                self.combo_subject.addItem(f"{s[1]} - {s[2]}", s[0])
            self.combo_subject.setStyleSheet("background-color: #374151; color: white; padding: 8px;")
            
            self.input_title = QLineEdit()
            self.input_title.setPlaceholderText("Assignment Title...")
            self.input_title.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            self.input_due = QLineEdit()
            self.input_due.setPlaceholderText("Due Date (YYYY-MM-DD)...")
            self.input_due.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            self.input_desc = QTextEdit()
            self.input_desc.setPlaceholderText("Description / Instructions...")
            self.input_desc.setMaximumHeight(80)
            self.input_desc.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            btn_create = QPushButton("Create Assignment")
            btn_create.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
            btn_create.clicked.connect(self._create_assignment)

            left_layout.addWidget(self.combo_subject)
            left_layout.addWidget(self.input_title)
            left_layout.addWidget(self.input_due)
            left_layout.addWidget(self.input_desc)
            left_layout.addWidget(btn_create)

        splitter.addWidget(left_widget)

        # Right Column: Submissions / Student Form
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        if self.role == "faculty":
            sub_lbl = QLabel("Student Submissions & Evaluation")
            sub_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #F59E0B;")
            right_layout.addWidget(sub_lbl)

            self.table_submissions = QTableWidget()
            self.table_submissions.setColumnCount(5)
            self.table_submissions.setHorizontalHeaderLabels(["Roll #", "Name", "Submitted At", "Marks", "Feedback"])
            self.table_submissions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.table_submissions.setStyleSheet("""
                QTableWidget { background-color: #1F2937; color: white; gridline-color: #374151; font-size: 13px; }
                QHeaderView::section { background-color: #111827; color: #F59E0B; font-weight: bold; }
            """)
            self.table_submissions.itemSelectionChanged.connect(self._on_submission_selected)
            right_layout.addWidget(self.table_submissions)

            # Grade & Feedback Controls
            grade_frame = QFrame()
            grade_frame.setStyleSheet("background-color: #1E293B; border-radius: 8px; padding: 10px;")
            gv = QVBoxLayout(grade_frame)
            
            self.lbl_selected_student = QLabel("Select a submission to grade")
            self.lbl_selected_student.setStyleSheet("font-weight: bold; color: #E5E7EB;")
            
            self.txt_submission_content = QTextEdit()
            self.txt_submission_content.setReadOnly(True)
            self.txt_submission_content.setPlaceholderText("Student Submission text / code...")
            self.txt_submission_content.setStyleSheet("background-color: #111827; color: #34D399; font-family: Consolas;")

            gh = QHBoxLayout()
            self.input_marks = QLineEdit()
            self.input_marks.setPlaceholderText("Score (e.g. 95)...")
            self.input_marks.setStyleSheet("background-color: #374151; color: white; padding: 8px;")
            
            btn_grade = QPushButton("Save Marks & Feedback")
            btn_grade.setStyleSheet("background-color: #D97706; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
            btn_grade.clicked.connect(self._save_grade)
            gh.addWidget(self.input_marks)
            gh.addWidget(btn_grade)

            self.input_feedback = QLineEdit()
            self.input_feedback.setPlaceholderText("Enter feedback for student...")
            self.input_feedback.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            gv.addWidget(self.lbl_selected_student)
            gv.addWidget(self.txt_submission_content)
            gv.addLayout(gh)
            gv.addWidget(self.input_feedback)
            right_layout.addWidget(grade_frame)

        else:
            # Student Submission Form
            sub_lbl = QLabel("Submit Assignment Work")
            sub_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #60A5FA;")
            right_layout.addWidget(sub_lbl)

            self.lbl_assignment_info = QLabel("Select an assignment on the left to view instructions & submit.")
            self.lbl_assignment_info.setStyleSheet("color: #94A3B8; font-size: 13px;")
            right_layout.addWidget(self.lbl_assignment_info)

            self.student_sub_text = QTextEdit()
            self.student_sub_text.setPlaceholderText("Type or paste your code/solution text here...")
            self.student_sub_text.setStyleSheet("background-color: #1F2937; color: white; font-family: Consolas; font-size: 13px; border: 1px solid #374151;")
            right_layout.addWidget(self.student_sub_text)

            file_layout = QHBoxLayout()
            self.input_filepath = QLineEdit()
            self.input_filepath.setPlaceholderText("Attached file path...")
            self.input_filepath.setStyleSheet("background-color: #1F2937; color: white; padding: 8px;")
            
            btn_browse = QPushButton("Attach File")
            btn_browse.setStyleSheet("background-color: #374151; color: white; padding: 8px;")
            btn_browse.clicked.connect(self._browse_file)
            file_layout.addWidget(self.input_filepath)
            file_layout.addWidget(btn_browse)
            right_layout.addLayout(file_layout)

            btn_submit = QPushButton(" Submit Assignment")
            btn_submit.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 12px; border-radius: 6px; font-size: 14px;")
            btn_submit.clicked.connect(self._submit_assignment)
            right_layout.addWidget(btn_submit)

        splitter.addWidget(right_widget)
        main_layout.addWidget(splitter)

        self.load_assignments()

    def load_assignments(self):
        rows = get_assignments()
        self.table_assignments.setRowCount(len(rows))
        for idx, r in enumerate(rows):
            self.table_assignments.setItem(idx, 0, QTableWidgetItem(str(r[0])))
            self.table_assignments.setItem(idx, 1, QTableWidgetItem(f"{r[1]} - {r[2]}"))
            self.table_assignments.setItem(idx, 2, QTableWidgetItem(r[3]))
            self.table_assignments.setItem(idx, 3, QTableWidgetItem(r[5]))

    def _on_assignment_selected(self):
        selected = self.table_assignments.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        assign_id = int(self.table_assignments.item(row, 0).text())
        
        if self.role == "faculty":
            submissions = get_assignment_submissions(assign_id)
            self.table_submissions.setRowCount(len(submissions))
            for idx, s in enumerate(submissions):
                # s: (sub_id, roll, name, sub_text, file_path, submitted_at, marks, feedback)
                self.table_submissions.setItem(idx, 0, QTableWidgetItem(s[1]))
                self.table_submissions.setItem(idx, 1, QTableWidgetItem(s[2]))
                self.table_submissions.setItem(idx, 2, QTableWidgetItem(s[5]))
                self.table_submissions.setItem(idx, 3, QTableWidgetItem(str(s[6])))
                self.table_submissions.setItem(idx, 4, QTableWidgetItem(s[7] or "No feedback"))
                # Store full s row data on item
                self.table_submissions.item(idx, 0).setData(Qt.UserRole, s)
        else:
            rows = get_assignments()
            target = next((r for r in rows if r[0] == assign_id), None)
            if target:
                self.lbl_assignment_info.setText(f"Subject: {target[1]} ({target[2]})\nTitle: {target[3]}\nDue Date: {target[5]}\nDescription: {target[4]}")

    def _on_submission_selected(self):
        if self.role != "faculty":
            return
        selected = self.table_submissions.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        sub_data = self.table_submissions.item(row, 0).data(Qt.UserRole)
        if sub_data:
            # sub_data: (sub_id, roll, name, sub_text, file_path, submitted_at, marks, feedback)
            self.current_sub_id = sub_data[0]
            self.lbl_selected_student.setText(f"Grading Student: {sub_data[2]} ({sub_data[1]})")
            self.txt_submission_content.setPlainText(f"Submission Text:\n{sub_data[3]}\n\nAttached File: {sub_data[4]}")
            self.input_marks.setText(str(sub_data[6]))
            self.input_feedback.setText(sub_data[7] or "")

    def _create_assignment(self):
        subject_id = self.combo_subject.currentData()
        title = self.input_title.text().strip()
        due = self.input_due.text().strip()
        desc = self.input_desc.toPlainText().strip()
        if not title or not due:
            QMessageBox.warning(self, "Validation Error", "Please provide title and due date.")
            return
        add_assignment(subject_id, title, desc, due)
        QMessageBox.information(self, "Success", "Assignment created successfully!")
        self.input_title.clear()
        self.input_due.clear()
        self.input_desc.clear()
        self.load_assignments()

    def _browse_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Submission File", "", "All Files (*.*)")
        if fname:
            self.input_filepath.setText(fname)

    def _submit_assignment(self):
        selected = self.table_assignments.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an assignment from the left table first.")
            return
        row = selected[0].row()
        assign_id = int(self.table_assignments.item(row, 0).text())
        sub_text = self.student_sub_text.toPlainText().strip()
        file_path = self.input_filepath.text().strip()

        if not sub_text and not file_path:
            QMessageBox.warning(self, "Warning", "Please enter submission text or attach a file.")
            return

        success = submit_assignment(assign_id, self.user[0], sub_text, file_path)
        if success:
            QMessageBox.information(self, "Success", "Assignment submitted successfully!")
            self.student_sub_text.clear()
            self.input_filepath.clear()
        else:
            QMessageBox.critical(self, "Error", "Failed to submit assignment. Student profile not found.")

    def _save_grade(self):
        if not hasattr(self, 'current_sub_id') or not self.current_sub_id:
            QMessageBox.warning(self, "Warning", "Select a student submission to grade.")
            return
        try:
            marks = float(self.input_marks.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Warning", "Please enter a valid numeric score.")
            return
        feedback = self.input_feedback.text().strip()
        grade_submission(self.current_sub_id, marks, feedback)
        QMessageBox.information(self, "Saved", "Grade and feedback saved successfully!")
        self._on_assignment_selected()
