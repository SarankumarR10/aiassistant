from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QFrame, QSplitter
)
from PySide6.QtCore import Qt
from datetime import date
from database.database import (
    get_subjects,
    get_assignments,
    add_assignment,
    get_assignment_submissions,
    get_student_assignment_submission,
    submit_assignment,
    grade_submission
)
from gui.theme import POSITIVUS_QSS, create_section_header

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
        self.setStyleSheet(POSITIVUS_QSS)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Title
        title_text = "Assignment Workspace & Grading" if self.role == "faculty" else "My Academic Assignments & Submissions"
        header = create_section_header(title_text)
        main_layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)

        # Left Column: Assignments List & Form
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)

        list_lbl = QLabel("Course Assignments List")
        list_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        left_layout.addWidget(list_lbl)

        self.table_assignments = QTableWidget()
        self.table_assignments.setColumnCount(4)
        self.table_assignments.setHorizontalHeaderLabels(["ID", "Subject", "Assignment Title", "Due Date"])
        self.table_assignments.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_assignments.itemSelectionChanged.connect(self._on_assignment_selected)
        left_layout.addWidget(self.table_assignments)

        if self.role == "faculty":
            form_card = QFrame()
            form_card.setObjectName("surfaceCard")
            form_card.setStyleSheet("""
                QFrame#surfaceCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                    padding: 14px;
                }
            """)
            fc_layout = QVBoxLayout(form_card)

            form_lbl = QLabel("Create New Assignment")
            form_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #0F172A;")
            fc_layout.addWidget(form_lbl)

            self.combo_subject = QComboBox()
            for s in self.subjects:
                self.combo_subject.addItem(f"{s[1]} - {s[2]}", s[0])
            
            self.input_title = QLineEdit()
            self.input_title.setPlaceholderText("Assignment Title...")

            self.input_due = QLineEdit()
            self.input_due.setPlaceholderText("Due Date (YYYY-MM-DD)...")

            self.input_desc = QTextEdit()
            self.input_desc.setPlaceholderText("Description / Instructions...")
            self.input_desc.setMaximumHeight(80)

            btn_create = QPushButton("Publish Assignment")
            btn_create.setCursor(Qt.PointingHandCursor)
            btn_create.setProperty("class", "secondary")
            btn_create.clicked.connect(self._create_assignment)

            fc_layout.addWidget(self.combo_subject)
            fc_layout.addWidget(self.input_title)
            fc_layout.addWidget(self.input_due)
            fc_layout.addWidget(self.input_desc)
            fc_layout.addWidget(btn_create)

            left_layout.addWidget(form_card)

        splitter.addWidget(left_widget)

        # Right Column: Submissions / Student Form
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        if self.role == "faculty":
            sub_lbl = QLabel("Student Submissions & Evaluation")
            sub_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
            right_layout.addWidget(sub_lbl)

            self.table_submissions = QTableWidget()
            self.table_submissions.setColumnCount(5)
            self.table_submissions.setHorizontalHeaderLabels(["Roll #", "Name", "Submitted At", "Marks", "Feedback"])
            self.table_submissions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.table_submissions.itemSelectionChanged.connect(self._on_submission_selected)
            right_layout.addWidget(self.table_submissions)

            grade_frame = QFrame()
            grade_frame.setObjectName("surfaceCard")
            grade_frame.setStyleSheet("""
                QFrame#surfaceCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                    padding: 14px;
                }
            """)
            gv = QVBoxLayout(grade_frame)
            
            self.lbl_selected_student = QLabel("Select a submission above to grade")
            self.lbl_selected_student.setStyleSheet("font-weight: 700; font-size: 13px; color: #0F172A;")
            
            self.txt_submission_content = QTextEdit()
            self.txt_submission_content.setReadOnly(True)
            self.txt_submission_content.setPlaceholderText("Student Submission text / code...")
            self.txt_submission_content.setStyleSheet("""
                QTextEdit {
                    background-color: #F8FAFC;
                    color: #0F172A;
                    font-family: 'Consolas', monospace;
                    font-size: 13px;
                }
            """)

            gh = QHBoxLayout()
            self.input_marks = QLineEdit()
            self.input_marks.setPlaceholderText("Score (e.g. 95)...")
            
            btn_grade = QPushButton("Save Grade")
            btn_grade.setCursor(Qt.PointingHandCursor)
            btn_grade.clicked.connect(self._save_grade)
            gh.addWidget(self.input_marks)
            gh.addWidget(btn_grade)

            self.input_feedback = QLineEdit()
            self.input_feedback.setPlaceholderText("Enter feedback for student...")

            gv.addWidget(self.lbl_selected_student)
            gv.addWidget(self.txt_submission_content)
            gv.addLayout(gh)
            gv.addWidget(self.input_feedback)
            right_layout.addWidget(grade_frame)

        else:
            sub_lbl = QLabel("Submit Assignment Work")
            sub_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
            right_layout.addWidget(sub_lbl)

            self.lbl_assignment_info = QLabel("Select an assignment on the left to view instructions & submit.")
            self.lbl_assignment_info.setWordWrap(True)
            self.lbl_assignment_info.setStyleSheet("color: #475569; font-size: 13px; font-weight: 500;")
            right_layout.addWidget(self.lbl_assignment_info)

            self.student_sub_text = QTextEdit()
            self.student_sub_text.setPlaceholderText("Type or paste your code / solution text here...")
            self.student_sub_text.setStyleSheet("""
                QTextEdit {
                    background-color: #FFFFFF;
                    color: #0F172A;
                    font-family: 'Consolas', monospace;
                    font-size: 13px;
                }
            """)
            right_layout.addWidget(self.student_sub_text)

            file_layout = QHBoxLayout()
            self.input_filepath = QLineEdit()
            self.input_filepath.setPlaceholderText("Attached file path...")
            
            btn_browse = QPushButton("Attach File")
            btn_browse.setCursor(Qt.PointingHandCursor)
            btn_browse.setProperty("class", "outline")
            btn_browse.clicked.connect(self._browse_file)
            file_layout.addWidget(self.input_filepath)
            file_layout.addWidget(btn_browse)
            right_layout.addLayout(file_layout)

            btn_submit = QPushButton("Submit Assignment Work")
            btn_submit.setCursor(Qt.PointingHandCursor)
            btn_submit.setProperty("class", "secondary")
            btn_submit.clicked.connect(self._submit_assignment)
            right_layout.addWidget(btn_submit)

        splitter.addWidget(right_widget)
        main_layout.addWidget(splitter)

        self._load_assignments()

    def _load_assignments(self):
        assignments = get_assignments()
        self.current_assignments = assignments
        self.table_assignments.setRowCount(len(assignments))
        for row, a in enumerate(assignments):
            self.table_assignments.setItem(row, 0, QTableWidgetItem(str(a[0])))
            self.table_assignments.setItem(row, 1, QTableWidgetItem(f"{a[1]} - {a[2]}"))
            self.table_assignments.setItem(row, 2, QTableWidgetItem(str(a[3])))
            self.table_assignments.setItem(row, 3, QTableWidgetItem(str(a[5])))

    def _create_assignment(self):
        subject_id = self.combo_subject.currentData()
        title = self.input_title.text().strip()
        due_date = self.input_due.text().strip()
        desc = self.input_desc.toPlainText().strip()

        if not title or not due_date:
            QMessageBox.warning(self, "Warning", "Title and Due Date are required.")
            return

        try:
            date.fromisoformat(due_date)
        except ValueError:
            QMessageBox.warning(self, "Invalid due date", "Use the date format YYYY-MM-DD.")
            return

        try:
            add_assignment(subject_id, title, desc, due_date, faculty_id=self.user[0])
        except Exception as exc:
            QMessageBox.critical(self, "Could not publish assignment", str(exc))
            return
        QMessageBox.information(self, "Success", f"Assignment '{title}' created successfully!")
        self.input_title.clear()
        self.input_due.clear()
        self.input_desc.clear()
        self._load_assignments()

    def _on_assignment_selected(self):
        selected_rows = self.table_assignments.selectedItems()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        assignment_id = int(self.table_assignments.item(row, 0).text())
        assignment = self.current_assignments[row]
        title = assignment[3]
        self.selected_assignment_id = assignment_id

        if self.role == "faculty":
            self._load_submissions(assignment_id)
        else:
            submission = get_student_assignment_submission(assignment_id, self.user[0])
            if submission:
                submitted_at, marks, feedback, content, file_path, graded_at = submission
                grade = f"Graded: {marks:g}/{assignment[6]}" if graded_at else "Awaiting grade"
                feedback_text = f"\nFeedback: {feedback}" if feedback else ""
                status = f"Submitted {submitted_at} · {grade}{feedback_text}"
                if content or file_path:
                    self.student_sub_text.setPlainText(content or "")
                    self.input_filepath.setText(file_path or "")
            else:
                status = "Not submitted yet"
                self.student_sub_text.clear()
                self.input_filepath.clear()
            instructions = assignment[4] or "No additional instructions provided."
            self.lbl_assignment_info.setText(
                f"{title}\nDue: {assignment[5]} · Maximum: {assignment[6]} marks\n\n"
                f"{instructions}\n\n{status}"
            )

    def _load_submissions(self, assignment_id: int):
        submissions = get_assignment_submissions(assignment_id)
        self.current_submissions = submissions
        self.table_submissions.setRowCount(len(submissions))
        for row, s in enumerate(submissions):
            self.table_submissions.setItem(row, 0, QTableWidgetItem(str(s[1])))
            self.table_submissions.setItem(row, 1, QTableWidgetItem(str(s[2])))
            self.table_submissions.setItem(row, 2, QTableWidgetItem(str(s[5])))
            maximum = next((a[6] for a in self.current_assignments if a[0] == assignment_id), 100)
            self.table_submissions.setItem(row, 3, QTableWidgetItem(f"{s[6]:g}/{maximum}" if s[8] and s[6] is not None else "Pending"))
            self.table_submissions.setItem(row, 4, QTableWidgetItem(str(s[7]) if s[7] else "-"))

    def _on_submission_selected(self):
        selected_rows = self.table_submissions.selectedItems()
        if not selected_rows or not hasattr(self, 'current_submissions'):
            return
        row = selected_rows[0].row()
        sub = self.current_submissions[row]
        self.selected_submission_id = sub[0]
        self.lbl_selected_student.setText(f"Grading Student: {sub[2]} ({sub[1]})")
        self.txt_submission_content.setText(sub[3] if sub[3] else f"[File Attached: {sub[4]}]")
        if sub[8] and sub[6] is not None:
            self.input_marks.setText(str(sub[6]))
        else:
            self.input_marks.clear()
        self.input_feedback.setText(sub[7] if sub[7] else "")


    def _save_grade(self):
        if not hasattr(self, 'selected_submission_id'):
            QMessageBox.warning(self, "Warning", "Please select a student submission to grade.")
            return
        marks = self.input_marks.text().strip()
        feedback = self.input_feedback.text().strip()
        try:
            score = float(marks)
            maximum = next(a[6] for a in self.current_assignments if a[0] == self.selected_assignment_id)
            if score < 0 or score > maximum:
                raise ValueError
        except (ValueError, StopIteration):
            QMessageBox.warning(self, "Warning", "Enter a score within the assignment’s mark limit.")
            return

        grade_submission(self.selected_submission_id, score, feedback, faculty_id=self.user[0])
        QMessageBox.information(self, "Success", "Grade and feedback saved successfully!")
        if hasattr(self, 'selected_assignment_id'):
            self._load_submissions(self.selected_assignment_id)

    def _browse_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Attach Submission File")
        if fname:
            self.input_filepath.setText(fname)

    def _submit_assignment(self):
        if not hasattr(self, 'selected_assignment_id'):
            QMessageBox.warning(self, "Warning", "Please select an assignment from the left table first.")
            return
        content = self.student_sub_text.toPlainText().strip()
        filepath = self.input_filepath.text().strip()
        if not content and not filepath:
            QMessageBox.warning(self, "Warning", "Please enter text/code solution or attach a file.")
            return

        if not submit_assignment(self.selected_assignment_id, self.user[0], content, filepath):
            QMessageBox.critical(self, "Submission failed", "Your student account could not be matched to a student record.")
            return
        QMessageBox.information(self, "Success", "Assignment submitted successfully!")
        self.student_sub_text.clear()
        self.input_filepath.clear()
