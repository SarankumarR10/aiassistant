from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QStackedWidget, QTextEdit,
    QLineEdit, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QDialog, QScrollArea, QGridLayout, QTimeEdit
)
from PySide6.QtCore import Qt, QTime, QTimer
from gui.attendance import AttendanceWindow
from gui.analytics_widget import ClassroomAnalyticsWidget
from gui.academics_widget import AcademicTrackerWidget
from gui.code_runner_widget import CodeRunnerWidget
from gui.lab_monitor_widget import LabMonitorWidget
from gui.lab_exam_widget import FacultyLabExamWidget
from gui.lab_review_widget import LabSubmissionReviewWidget
from gui.voice_notes_widget import VoiceNotesWidget
from gui.speech_worker import SpeechInputWorker
from gui.assignments_widget import AssignmentsWidget
from gui.notes_qbank_widget import NotesAndQuestionBankWidget
from gui.notices_widget import NoticesAndRemindersWidget
from reports.report_generator import report_generator
from ai.rag_engine import rag_engine
from voice.voice_engine import voice_engine
from voice.commands import execute_voice_intent
from database.database import (
    get_timetables, get_subjects, get_assignments, get_notes, add_announcement,
    add_timetable_entry, update_timetable_entry, delete_timetable_entry,
    get_dashboard_stats_faculty, get_students, add_student, update_student, delete_student
)
from gui.theme import POSITIVUS_QSS, create_pill_badge, create_section_header, create_content_scroll_area, COLOR_PRIMARY, COLOR_SECONDARY, COLOR_NEUTRAL_BG, style_action_button
from voice.speech_input import speech_input_status


class StudentDirectoryWidget(QWidget):
    """
    Complete Student Directory & Management Widget supporting full CRUD operations.
    """
    def __init__(self, faculty_id):
        super().__init__()
        self.faculty_id = faculty_id
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = create_section_header("Student Directory & Records Management", "Create, search, update, or remove student accounts in SQLite database")
        layout.addWidget(header)

        # Top Bar: Search + Add Button
        top_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search student by name or roll number...")
        self.search_input.textChanged.connect(self.filter_students)

        btn_add = QPushButton("Add New Student")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setProperty("class", "secondary")
        btn_add.clicked.connect(self.show_add_student_dialog)

        top_bar.addWidget(self.search_input, 1)
        top_bar.addWidget(btn_add)
        layout.addLayout(top_bar)

        # Student Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Roll Number", "Name", "Department", "Year", "Section", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self.load_students()

    def load_students(self):
        self.all_students = get_students()
        self.filter_students()

    def filter_students(self):
        query = self.search_input.text().lower().strip()
        filtered = [s for s in self.all_students if query in s[1].lower() or query in s[2].lower() or query in s[3].lower()]

        self.table.setRowCount(len(filtered))
        for row, st in enumerate(filtered):
            # st: (id, roll_number, name, department, year, section)
            student_id = st[0]
            self.table.setItem(row, 0, QTableWidgetItem(str(st[0])))
            self.table.setItem(row, 1, QTableWidgetItem(str(st[1])))
            self.table.setItem(row, 2, QTableWidgetItem(str(st[2])))
            self.table.setItem(row, 3, QTableWidgetItem(str(st[3])))
            self.table.setItem(row, 4, QTableWidgetItem(f"Year {st[4]}"))
            self.table.setItem(row, 5, QTableWidgetItem(str(st[5])))

            # Action Buttons Layout
            action_widget = QWidget()
            act_layout = QHBoxLayout(action_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            btn_edit = QPushButton("Edit")
            btn_edit.setProperty("class", "outline")
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.clicked.connect(lambda _, s=st: self.show_edit_student_dialog(s))

            btn_del = QPushButton("Delete")
            btn_del.setProperty("class", "danger")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.clicked.connect(lambda _, sid=student_id, sname=st[2]: self.delete_student_record(sid, sname))

            act_layout.addWidget(btn_edit)
            act_layout.addWidget(btn_del)
            self.table.setCellWidget(row, 6, action_widget)

    def show_add_student_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Student Record")
        dialog.setMinimumSize(420, 380)
        d_layout = QVBoxLayout(dialog)

        title = QLabel("Create Student Account")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        d_layout.addWidget(title)

        inp_user = QLineEdit()
        inp_user.setPlaceholderText("Username (e.g. student6)...")
        inp_roll = QLineEdit()
        inp_roll.setPlaceholderText("Roll Number (e.g. 23CSE006)...")
        inp_name = QLineEdit()
        inp_name.setPlaceholderText("Full Name...")
        inp_dept = QLineEdit("CSE")
        inp_year = QComboBox()
        inp_year.addItems(["1", "2", "3", "4"])
        inp_year.setCurrentText("3")
        inp_sec = QLineEdit("C")
        inp_pass = QLineEdit("student123")

        d_layout.addWidget(QLabel("Username:"))
        d_layout.addWidget(inp_user)
        d_layout.addWidget(QLabel("Roll Number:"))
        d_layout.addWidget(inp_roll)
        d_layout.addWidget(QLabel("Full Name:"))
        d_layout.addWidget(inp_name)
        d_layout.addWidget(QLabel("Department:"))
        d_layout.addWidget(inp_dept)
        d_layout.addWidget(QLabel("Year & Section:"))
        h = QHBoxLayout()
        h.addWidget(inp_year)
        h.addWidget(inp_sec)
        d_layout.addLayout(h)
        d_layout.addWidget(QLabel("Initial Password:"))
        d_layout.addWidget(inp_pass)

        btn_save = QPushButton("Create Student")
        btn_save.setProperty("class", "secondary")
        def save():
            u, r, n = inp_user.text().strip(), inp_roll.text().strip(), inp_name.text().strip()
            if not u or not r or not n:
                QMessageBox.warning(dialog, "Warning", "Username, Roll Number, and Name are required.")
                return
            try:
                add_student(u, r, n, inp_dept.text().strip(), int(inp_year.currentText()), inp_sec.text().strip(), inp_pass.text(), self.faculty_id)
                QMessageBox.information(self, "Success", f"Student '{n}' created successfully!")
                dialog.accept()
                self.load_students()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to create student: {e}")

        btn_save.clicked.connect(save)
        d_layout.addWidget(btn_save)
        dialog.exec()

    def show_edit_student_dialog(self, st):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Student Record - {st[2]}")
        dialog.setMinimumSize(420, 320)
        d_layout = QVBoxLayout(dialog)

        title = QLabel(f"Update Details for {st[2]}")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        d_layout.addWidget(title)

        inp_roll = QLineEdit(st[1])
        inp_name = QLineEdit(st[2])
        inp_dept = QLineEdit(st[3])
        inp_year = QComboBox()
        inp_year.addItems(["1", "2", "3", "4"])
        inp_year.setCurrentText(str(st[4]))
        inp_sec = QLineEdit(st[5])

        d_layout.addWidget(QLabel("Roll Number:"))
        d_layout.addWidget(inp_roll)
        d_layout.addWidget(QLabel("Full Name:"))
        d_layout.addWidget(inp_name)
        d_layout.addWidget(QLabel("Department:"))
        d_layout.addWidget(inp_dept)
        d_layout.addWidget(QLabel("Year & Section:"))
        h = QHBoxLayout()
        h.addWidget(inp_year)
        h.addWidget(inp_sec)
        d_layout.addLayout(h)

        btn_save = QPushButton("Save Changes")
        btn_save.setProperty("class", "secondary")
        def save():
            r, n = inp_roll.text().strip(), inp_name.text().strip()
            if not r or not n:
                QMessageBox.warning(dialog, "Warning", "Roll Number and Name are required.")
                return
            try:
                update_student(st[0], r, n, inp_dept.text().strip(), int(inp_year.currentText()), inp_sec.text().strip(), self.faculty_id)
                QMessageBox.information(self, "Success", "Student record updated!")
                dialog.accept()
                self.load_students()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to update: {e}")

        btn_save.clicked.connect(save)
        d_layout.addWidget(btn_save)
        dialog.exec()

    def delete_student_record(self, student_id: int, student_name: str):
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete student '{student_name}'?\nThis will remove their user account and records.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            delete_student(student_id, self.faculty_id)
            QMessageBox.information(self, "Deleted", "Student record deleted successfully.")
            self.load_students()


class FacultyDashboard(QMainWindow):

    def __init__(self, user, logout_callback):
        super().__init__()
        self.user = user
        self.logout_callback = logout_callback

        self.setWindowTitle("EduPilot Workspace - Faculty Portal")
        self.setMinimumSize(1024, 680)
        self.resize(1280, 800)

        self.build_ui()

    def build_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------- LIGHT NEUTRAL SIDEBAR ----------------
        sidebar = QFrame()
        sidebar.setObjectName("appSidebar")
        sidebar.setFixedWidth(252)
        sidebar.setStyleSheet("""
            QFrame#appSidebar {
                background-color: #FFFFFF;
                border-right: 1px solid #DCE2E7;
            }
            QLabel {
                color: #26323B;
            }
            QPushButton {
                background-color: transparent;
                color: #596A75;
                border: none;
                padding: 9px 12px;
                text-align: left;
                font-size: 13px;
                font-weight: 500;
                border-radius: 6px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #F0F3F5;
                color: #26323B;
            }
            QPushButton:checked {
                background-color: #E8EEF2;
                color: #263746;
                border-left: 3px solid #48677D;
                font-weight: 600;
            }
        """)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)

        brand_title = QLabel("EDUPILOT")
        brand_title.setStyleSheet("font-size: 18px; font-weight: 750; color: #263746; letter-spacing: 0.4px;")
        subtitle = QLabel("Faculty Workspace")
        subtitle.setStyleSheet("color: #75838C; font-size: 12px; font-weight: 400;")

        sidebar_layout.addWidget(brand_title)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(16)

        nav_area = QScrollArea()
        nav_area.setWidgetResizable(True)
        nav_area.setFrameShape(QFrame.NoFrame)
        nav_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_area.setStyleSheet("QScrollArea, QScrollArea QWidget { background: transparent; }")
        nav_content = QWidget()
        nav_layout = QVBoxLayout(nav_content)
        nav_layout.setContentsMargins(0, 0, 4, 0)
        nav_layout.setSpacing(4)
        nav_area.setWidget(nav_content)

        nav_items = [
            ("Overview", 0),
            ("Attendance Register", 1),
            ("Student Directory", 2),
            ("Classroom Analytics", 3),
            ("Academic Records", 4),
            ("Assignments and Grading", 5),
            ("Knowledge Base and Notes", 6),
            ("Notices and Reminders", 7),
            ("Lab Workstation", 8),
            ("Code Runner", 9),
            ("AI Tutor / Local RAG", 10),
            ("Schedule / Timetable", 11),
            ("Voice Assistant", 12),
            ("Voice Notes", 13),
            ("Practical Exam Management", 14),
            ("Lab Submission Review", 15),
        ]

        self.nav_buttons = []
        for text, page_idx in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=page_idx: self.switch_page(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_layout.addStretch()
        sidebar_layout.addWidget(nav_area, 1)

        logout_button = QPushButton("Sign Out")
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #596A75;
                border: 1px solid #D5DDE2;
                font-weight: 600;
                padding: 9px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #F0F3F5;
                color: #26323B;
                border: 1px solid #C8D1D7;
            }
        """)
        logout_button.clicked.connect(self.logout)
        sidebar_layout.addWidget(logout_button)

        # ---------------- STACKED PAGES ----------------
        self.stack = QStackedWidget()
        self.code_runner_widget = CodeRunnerWidget()

        pages = (
            self._build_overview_page(), self._build_attendance_page(),
            StudentDirectoryWidget(self.user[0]), ClassroomAnalyticsWidget(),
            AcademicTrackerWidget(self.user, role="faculty"),
            AssignmentsWidget(self.user, role="faculty"),
            NotesAndQuestionBankWidget(self.user, role="faculty"),
            NoticesAndRemindersWidget(self.user, role="faculty"),
            LabMonitorWidget(), self.code_runner_widget, self._build_ai_rag_page(),
            self._build_timetable_page(), self._build_voice_page(),
            VoiceNotesWidget(self.user), FacultyLabExamWidget(self.user[0]),
            LabSubmissionReviewWidget(self.user[0]),
        )
        for page in pages:
            self.stack.addWidget(create_content_scroll_area(page))

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        self.switch_page(0)

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)

        header = create_section_header("Overview Dashboard", f"Welcome back, Prof. {self.user[3]}")
        layout.addWidget(header)
        layout.addSpacing(16)

        stats = get_dashboard_stats_faculty()
        attendance_value = (
            f"{stats['attendance_pct']}%" if stats["attendance_pct"] is not None else "—"
        )
        attendance_caption = (
            "Average of recorded registers"
            if stats["attendance_records"] else "No attendance registers yet"
        )

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)
        cards_layout.addWidget(self._create_card("Total Students", f"{stats['total_students']}", "Enrolled in CSE-C"))
        cards_layout.addWidget(self._create_card("Overall Attendance", attendance_value, attendance_caption, accent=True))
        cards_layout.addWidget(self._create_card("Published Assignments", f"{stats['total_assignments']}", "Active Course Work"))
        cards_layout.addWidget(self._create_card("Department Notices", f"{stats['total_notices']}", "Announcements Posted", primary=True))

        layout.addLayout(cards_layout)
        layout.addSpacing(20)

        quick_header = create_section_header("Quick Actions & Report Generators")
        layout.addWidget(quick_header)
        layout.addSpacing(10)

        q_layout = QHBoxLayout()
        btn1 = QPushButton("Attendance Register")
        style_action_button(btn1, "primary")
        btn1.setCursor(Qt.PointingHandCursor)
        btn1.clicked.connect(lambda: self.switch_page(1))

        btn2 = QPushButton("Student Directory")
        style_action_button(btn2, "primary")
        btn2.setCursor(Qt.PointingHandCursor)
        btn2.clicked.connect(lambda: self.switch_page(2))

        btn3 = QPushButton("Assignments and Grading")
        style_action_button(btn3, "outline")
        btn3.setCursor(Qt.PointingHandCursor)
        btn3.clicked.connect(lambda: self.switch_page(5))

        q_layout.addWidget(btn1)
        q_layout.addWidget(btn2)
        q_layout.addWidget(btn3)
        layout.addLayout(q_layout)

        layout.addSpacing(16)

        # Export Actions Bar Card
        export_card = QFrame()
        export_card.setObjectName("surfaceCard")
        export_card.setStyleSheet("""
            QFrame#surfaceCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        exp_layout = QVBoxLayout(export_card)
        exp_lbl = QLabel("Academic & Attendance Data Export")
        exp_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        exp_layout.addWidget(exp_lbl)

        btn_grid = QGridLayout()
        btn_grid.setHorizontalSpacing(10)
        btn_grid.setVerticalSpacing(8)
        btn_exp_csv = QPushButton("Export Attendance CSV")
        style_action_button(btn_exp_csv, "primary")
        btn_exp_csv.setCursor(Qt.PointingHandCursor)
        btn_exp_csv.clicked.connect(self._export_attendance_csv)

        btn_exp_html = QPushButton("Export Printable HTML Report")
        style_action_button(btn_exp_html, "outline")
        btn_exp_html.setCursor(Qt.PointingHandCursor)
        btn_exp_html.clicked.connect(self._export_attendance_html)

        btn_exp_xlsx = QPushButton("Export Excel Workbook")
        style_action_button(btn_exp_xlsx, "outline")
        btn_exp_xlsx.clicked.connect(self._export_attendance_xlsx)

        btn_exp_pdf = QPushButton("Export PDF Report")
        style_action_button(btn_exp_pdf, "outline")
        btn_exp_pdf.clicked.connect(self._export_attendance_pdf)

        btn_grid.addWidget(btn_exp_csv, 0, 0)
        btn_grid.addWidget(btn_exp_html, 0, 1)
        btn_grid.addWidget(btn_exp_xlsx, 1, 0)
        btn_grid.addWidget(btn_exp_pdf, 1, 1)
        btn_grid.setColumnStretch(0, 1)
        btn_grid.setColumnStretch(1, 1)
        exp_layout.addLayout(btn_grid)
        layout.addWidget(export_card)
        layout.addStretch()

        return page

    def _create_card(self, title, val, desc, accent=False, primary=False):
        frame = QFrame()
        frame.setObjectName("dashboardMetricCard")
        bg, text_color, sub_color, border_color = "#FFFFFF", "#26323B", "#687782", "#DCE2E7"

        frame.setStyleSheet(f"""
            QFrame#dashboardMetricCard {{
                background-color: {bg};
                border: 1px solid {border_color};
                border-radius: 9px;
            }}
            QLabel {{
                color: {text_color};
            }}
        """)
        v = QVBoxLayout(frame)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(5)
        frame.setMinimumHeight(126)
        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet(f"color: {sub_color}; font-size: 12px; font-weight: 600;")
        v_lbl = QLabel(val)
        v_lbl.setStyleSheet(f"font-size: 25px; font-weight: 700; color: {text_color};")
        d = QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet(f"color: {sub_color}; font-size: 11px; font-weight: 400;")
        v.addWidget(t)
        v.addWidget(v_lbl)
        v.addWidget(d)
        return frame

    def _build_attendance_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)

        layout.addWidget(create_section_header("Attendance Module", "Camera Face Validation, Dynamic QR Code, and Manual Marking"))
        layout.addSpacing(16)

        card = QFrame()
        card.setObjectName("surfaceCard")
        card.setStyleSheet("""
            QFrame#surfaceCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        card_layout = QVBoxLayout(card)

        desc = QLabel("Record session attendance with anti-proxy validation, generate instant defaulter summaries, and export compliant reports.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569; font-size: 13px; font-weight: 400; margin-bottom: 12px;")
        card_layout.addWidget(desc)

        launch_btn = QPushButton("Launch Attendance Register Window")
        launch_btn.setCursor(Qt.PointingHandCursor)
        launch_btn.setProperty("class", "secondary")
        launch_btn.clicked.connect(self._open_attendance_window)
        card_layout.addWidget(launch_btn)

        layout.addWidget(card)
        layout.addSpacing(16)

        rep_header = create_section_header("Report Generation")
        layout.addWidget(rep_header)
        layout.addSpacing(10)

        h = QHBoxLayout()
        b1 = QPushButton("Export Attendance CSV Spreadsheet")
        b1.setCursor(Qt.PointingHandCursor)
        b1.clicked.connect(self._export_attendance_csv)

        b2 = QPushButton("Export Printable Attendance Summary (HTML)")
        b2.setCursor(Qt.PointingHandCursor)
        b2.setProperty("class", "outline")
        b2.clicked.connect(self._export_attendance_html)

        b3 = QPushButton("Export Attendance PDF")
        b3.setProperty("class", "outline")
        b3.clicked.connect(self._export_attendance_pdf)

        h.addWidget(b1)
        h.addWidget(b2)
        h.addWidget(b3)
        layout.addLayout(h)

        layout.addStretch()
        return page

    def _export_attendance_csv(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Attendance CSV", "Attendance_Report.csv", "CSV Files (*.csv)")
        if fname:
            report_generator.export_attendance_csv(fname)
            QMessageBox.information(self, "Success", f"Attendance CSV saved to:\n{fname}")

    def _export_attendance_html(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Attendance Report HTML", "Attendance_Summary.html", "HTML Files (*.html)")
        if fname:
            report_generator.export_attendance_html_report(fname)
            QMessageBox.information(self, "Success", f"Attendance HTML report saved to:\n{fname}")

    def _export_attendance_xlsx(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Attendance Workbook", "Attendance_Report.xlsx", "Excel Workbooks (*.xlsx)")
        if fname:
            report_generator.export_attendance_xlsx(fname)
            QMessageBox.information(self, "Success", f"Attendance workbook saved to:\n{fname}")

    def _export_attendance_pdf(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Attendance PDF", "Attendance_Report.pdf", "PDF Files (*.pdf)")
        if fname:
            try:
                report_generator.export_attendance_pdf_report(fname)
                QMessageBox.information(self, "Success", f"Attendance PDF saved to:\n{fname}")
            except Exception as error:
                QMessageBox.critical(self, "Could not export PDF", str(error))

    def _open_attendance_window(self):
        self.att_win = AttendanceWindow(self.user[0])
        self.att_win.show()

    def _build_ai_rag_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)

        layout.addWidget(create_section_header("AI Study Tutor & Local RAG Engine", "Search offline course documents, syllabi, and lab manuals"))
        layout.addSpacing(12)

        self.rag_input = QLineEdit()
        self.rag_input.setPlaceholderText("Enter your question (e.g., 'Explain Unit 3', 'What is JVM?', 'What is Normalization?')...")

        ask_btn = QPushButton("Search Local Knowledgebase")
        ask_btn.setCursor(Qt.PointingHandCursor)
        ask_btn.setProperty("class", "secondary")
        ask_btn.clicked.connect(self._on_ask_rag)

        layout.addWidget(self.rag_input)
        layout.addWidget(ask_btn)
        layout.addSpacing(10)

        self.rag_output = QTextEdit()
        self.rag_output.setReadOnly(True)
        self.rag_output.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                font-size: 13px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.rag_output)

        return page

    def _on_ask_rag(self):
        query = self.rag_input.text().strip()
        if not query:
            return
        res = rag_engine.query(query, role="faculty")
        self.rag_output.setPlainText(f"Answer:\n{res['answer']}\n\n[Source: {res['source']} | Confidence: {res['confidence']}]")

    def _build_timetable_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)

        layout.addWidget(create_section_header(
            "Faculty Timetable & Schedule", "Manage classes and avoid overlapping faculty or room bookings."
        ))
        layout.addSpacing(12)

        self.timetable_table = QTableWidget(0, 5)
        self.timetable_table.setHorizontalHeaderLabels(["Day", "Start", "End", "Subject", "Room"])
        self.timetable_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.timetable_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.timetable_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.timetable_table.setSelectionMode(QTableWidget.SingleSelection)
        self.timetable_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.timetable_table, 1)

        form = QHBoxLayout()
        self.timetable_subject = QComboBox()
        for subject_id, code, name in get_subjects():
            self.timetable_subject.addItem(f"{code} — {name}", subject_id)
        self.timetable_day = QComboBox()
        self.timetable_day.addItems(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        self.timetable_start = QTimeEdit(QTime(9, 0))
        self.timetable_start.setDisplayFormat("HH:mm")
        self.timetable_end = QTimeEdit(QTime(10, 0))
        self.timetable_end.setDisplayFormat("HH:mm")
        self.timetable_room = QLineEdit()
        self.timetable_room.setPlaceholderText("Room or lab")
        form.addWidget(self.timetable_subject, 2)
        form.addWidget(self.timetable_day)
        form.addWidget(self.timetable_start)
        form.addWidget(self.timetable_end)
        form.addWidget(self.timetable_room, 1)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.timetable_add_button = QPushButton("Add Class")
        self.timetable_add_button.clicked.connect(self._add_timetable_entry)
        self.timetable_update_button = QPushButton("Save Changes")
        self.timetable_update_button.setProperty("class", "outline")
        self.timetable_update_button.setEnabled(False)
        self.timetable_update_button.clicked.connect(self._update_timetable_entry)
        self.timetable_delete_button = QPushButton("Delete Selected")
        self.timetable_delete_button.setProperty("class", "danger")
        self.timetable_delete_button.setEnabled(False)
        self.timetable_delete_button.clicked.connect(self._delete_timetable_entry)
        actions.addWidget(self.timetable_add_button)
        actions.addWidget(self.timetable_update_button)
        actions.addWidget(self.timetable_delete_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.timetable_table.itemSelectionChanged.connect(self._select_timetable_entry)
        self._refresh_timetable()
        return page

    def _refresh_timetable(self):
        self.timetable_rows = get_timetables()
        self.timetable_table.setRowCount(len(self.timetable_rows))
        for row, entry in enumerate(self.timetable_rows):
            values = (entry[3], entry[4], entry[5], f"{entry[1]} — {entry[2]}", entry[6])
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.UserRole, entry[0])
                self.timetable_table.setItem(row, column, item)
        self.timetable_update_button.setEnabled(False)
        self.timetable_delete_button.setEnabled(False)
        self.timetable_selected_id = None

    def _select_timetable_entry(self):
        row = self.timetable_table.currentRow()
        if row < 0:
            return
        entry_id = self.timetable_table.item(row, 0).data(Qt.UserRole)
        entry = next((item for item in self.timetable_rows if item[0] == entry_id), None)
        if not entry:
            return
        self.timetable_selected_id = entry_id
        subject_id = next((sid for sid, code, _ in get_subjects() if code == entry[1]), None)
        self.timetable_subject.setCurrentIndex(max(0, self.timetable_subject.findData(subject_id)))
        self.timetable_day.setCurrentText(entry[3])
        self.timetable_start.setTime(QTime.fromString(entry[4], "HH:mm"))
        self.timetable_end.setTime(QTime.fromString(entry[5], "HH:mm"))
        self.timetable_room.setText(entry[6])
        can_manage = entry[7] == self.user[0]
        self.timetable_update_button.setEnabled(can_manage)
        self.timetable_delete_button.setEnabled(can_manage)

    def _timetable_form_values(self):
        return (self.timetable_subject.currentData(), self.timetable_day.currentText(),
                self.timetable_start.time().toString("HH:mm"), self.timetable_end.time().toString("HH:mm"),
                self.timetable_room.text().strip(), self.user[0])

    def _add_timetable_entry(self):
        try:
            add_timetable_entry(*self._timetable_form_values())
            self._refresh_timetable()
        except Exception as error:
            QMessageBox.warning(self, "Could not add class", str(error))

    def _update_timetable_entry(self):
        if self.timetable_selected_id is None:
            return
        try:
            update_timetable_entry(self.timetable_selected_id, *self._timetable_form_values())
            self._refresh_timetable()
        except Exception as error:
            QMessageBox.warning(self, "Could not save changes", str(error))

    def _delete_timetable_entry(self):
        if self.timetable_selected_id is None:
            return
        choice = QMessageBox.question(self, "Delete timetable entry", "Delete the selected class from your timetable?",
                                      QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if choice != QMessageBox.Yes:
            return
        try:
            delete_timetable_entry(self.timetable_selected_id, self.user[0])
            self._refresh_timetable()
        except Exception as error:
            QMessageBox.warning(self, "Could not delete class", str(error))

    def _build_voice_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)

        layout.addWidget(create_section_header("Voice Command Console", "Type a command; app launches ask for confirmation"))
        layout.addSpacing(12)

        self.voice_cmd_input = QLineEdit()
        self.voice_cmd_input.setPlaceholderText("Type a command (e.g., 'open VS Code', 'read schedule', 'start timer for 5 minutes')")

        send_voice_btn = QPushButton("Execute Command")
        send_voice_btn.setCursor(Qt.PointingHandCursor)
        send_voice_btn.clicked.connect(self._on_voice_cmd)

        layout.addWidget(self.voice_cmd_input)
        layout.addWidget(send_voice_btn)
        microphone_row = QHBoxLayout()
        speech_ready, speech_message = speech_input_status()
        self.speech_status_label = QLabel(speech_message)
        self.speech_status_label.setWordWrap(True)
        self.speech_status_label.setStyleSheet("color: #687782; font-size: 12px;")
        self.speech_start_button = QPushButton("Start Microphone")
        self.speech_start_button.setProperty("class", "outline")
        self.speech_start_button.setEnabled(speech_ready)
        self.speech_start_button.clicked.connect(self._start_speech_input)
        self.speech_stop_button = QPushButton("Stop Listening")
        self.speech_stop_button.setProperty("class", "outline")
        self.speech_stop_button.setEnabled(False)
        self.speech_stop_button.clicked.connect(self._stop_speech_input)
        microphone_row.addWidget(self.speech_start_button)
        microphone_row.addWidget(self.speech_stop_button)
        microphone_row.addWidget(self.speech_status_label, 1)
        layout.addLayout(microphone_row)
        self.speech_worker = None
        self.speech_error = ""
        timer_controls = QHBoxLayout()
        self.voice_timer_label = QLabel("No active timer")
        self.voice_timer_label.setStyleSheet("color: #687782; font-weight: 600;")
        self.voice_timer_cancel = QPushButton("Cancel Timer")
        self.voice_timer_cancel.setProperty("class", "outline")
        self.voice_timer_cancel.setEnabled(False)
        self.voice_timer_cancel.clicked.connect(self._cancel_voice_timer)
        timer_controls.addWidget(self.voice_timer_label)
        timer_controls.addStretch()
        timer_controls.addWidget(self.voice_timer_cancel)
        layout.addLayout(timer_controls)
        self.voice_timer = QTimer(self)
        self.voice_timer.timeout.connect(self._tick_voice_timer)
        self.voice_seconds_remaining = 0
        layout.addSpacing(10)

        self.voice_log = QTextEdit()
        self.voice_log.setReadOnly(True)
        self.voice_log.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                border: 1px solid #0F172A;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.voice_log)

        return page

    def _on_voice_cmd(self):
        text = self.voice_cmd_input.text().strip()
        if not text:
            return
        intent = voice_engine.process_command(text)
        if intent.get("intent") == "launch_app":
            choice = QMessageBox.question(self, "Confirm application launch", intent["reply"],
                                          QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if choice == QMessageBox.Yes:
                try:
                    res = voice_engine.launch_confirmed_app(intent["executable"], intent["app"])
                except Exception as error:
                    res = str(error)
            else:
                res = "Application launch cancelled."
        elif intent.get("intent") == "start_timer" and intent.get("status") == "success":
            self.voice_seconds_remaining = intent["duration_seconds"]
            self.voice_timer.start(1000)
            self.voice_timer_cancel.setEnabled(True)
            self._tick_voice_timer()
            res = intent["reply"]
        elif intent.get("intent") == "start_timer":
            res = intent.get("reply", "The timer could not be started.")
        elif intent.get("intent") in {"run_python", "compile_java"}:
            language = "Python" if intent["intent"] == "run_python" else "Java"
            self.code_runner_widget.lang_combo.setCurrentText(language)
            self.switch_page(9)
            self.code_runner_widget.output_edit.setPlainText(
                f"{language} sample loaded. No code has been run. Review the source and choose Run Code to confirm isolated execution."
            )
            res = (f"{language} code runner opened with a sample program. Review the code and choose Run Code "
                   "to confirm isolated execution.")
        elif intent.get("intent") == "create_project":
            self.switch_page(9)
            self.code_runner_widget.output_edit.setPlainText(
                "No project has been created. Choose New Project to set its name, language, and parent folder."
            )
            res = "Code Runner opened. Choose New Project and confirm the destination to create starter files."
        else:
            res = execute_voice_intent(intent, user_id=self.user[0], role="faculty")
        self.voice_log.append(f"> {text}\n[Assistant]: {res}\n")
        self.voice_cmd_input.clear()

    def _start_speech_input(self):
        if self.speech_worker and self.speech_worker.isRunning():
            return
        ready, explanation = speech_input_status()
        if not ready:
            self.speech_status_label.setText(explanation)
            return
        self.speech_error = ""
        self.speech_status_label.setText("Listening offline… say a command, then pause.")
        self.speech_start_button.setEnabled(False)
        self.speech_stop_button.setEnabled(True)
        self.speech_worker = SpeechInputWorker(self)
        self.speech_worker.phrase_recognized.connect(self._process_spoken_command)
        self.speech_worker.failed.connect(self._speech_input_failed)
        self.speech_worker.finished.connect(self._speech_input_finished)
        self.speech_worker.start()

    def _process_spoken_command(self, phrase: str):
        self.voice_cmd_input.setText(phrase)
        self._on_voice_cmd()

    def _speech_input_failed(self, message: str):
        self.speech_error = message

    def _speech_input_finished(self):
        ready, explanation = speech_input_status()
        self.speech_start_button.setEnabled(ready)
        self.speech_stop_button.setEnabled(False)
        self.speech_status_label.setText(self.speech_error or ("Microphone stopped." if ready else explanation))

    def _stop_speech_input(self):
        if self.speech_worker and self.speech_worker.isRunning():
            self.speech_status_label.setText("Stopping microphone…")
            self.speech_stop_button.setEnabled(False)
            self.speech_worker.request_stop()

    def closeEvent(self, event):
        if self.speech_worker and self.speech_worker.isRunning():
            self.speech_worker.request_stop()
            self.speech_worker.wait()
        super().closeEvent(event)

    def _tick_voice_timer(self):
        minutes, seconds = divmod(self.voice_seconds_remaining, 60)
        self.voice_timer_label.setText(f"Time remaining: {minutes:02d}:{seconds:02d}")
        if self.voice_seconds_remaining <= 0:
            self.voice_timer.stop()
            self.voice_timer_label.setText("Timer complete")
            self.voice_timer_cancel.setEnabled(False)
            voice_engine.speak("Your classroom timer is complete.")
            return
        self.voice_seconds_remaining -= 1

    def _cancel_voice_timer(self):
        self.voice_timer.stop()
        self.voice_seconds_remaining = 0
        self.voice_timer_label.setText("Timer cancelled")
        self.voice_timer_cancel.setEnabled(False)

    def logout(self):
        self.close()
        self.logout_callback()
