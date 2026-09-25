from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QStackedWidget, QTextEdit,
    QLineEdit, QListWidget, QFileDialog, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from gui.student_attendance import StudentAttendanceWindow
from gui.academics_widget import AcademicTrackerWidget
from gui.code_runner_widget import CodeRunnerWidget
from gui.assignments_widget import AssignmentsWidget
from gui.notes_qbank_widget import NotesAndQuestionBankWidget
from gui.notices_widget import NoticesAndRemindersWidget
from gui.speech_worker import SpeechInputWorker
from gui.voice_notes_widget import VoiceNotesWidget
from reports.report_generator import report_generator
from ai.rag_engine import rag_engine
from voice.voice_engine import voice_engine
from voice.commands import execute_voice_intent
from lab.lab_exam import lab_exam_assistant
from database.database import (
    get_student_attendance, get_timetables, get_reminders,
    get_dashboard_stats_student, get_student_lab_progress, submit_lab_experiment
)
from gui.theme import POSITIVUS_QSS, create_pill_badge, create_section_header, create_content_scroll_area, configure_wrapped_list, COLOR_PRIMARY, COLOR_SECONDARY, COLOR_NEUTRAL_BG, style_action_button
from voice.speech_input import speech_input_status


class StudentDashboard(QMainWindow):

    def __init__(self, user, logout_callback):
        super().__init__()
        self.user = user
        self.logout_callback = logout_callback

        self.setWindowTitle("EduPilot Workspace - Student Portal")
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
        subtitle = QLabel("Student Workspace")
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
            ("My Attendance", 1),
            ("Academic Records", 2),
            ("Assignments", 3),
            ("Notes and Question Bank", 4),
            ("Class Notices", 5),
            ("AI Study Tutor", 6),
            ("Local Code Runner", 7),
            ("Lab Manuals and Progress", 8),
            ("Timetable / Schedule", 9),
            ("Lab Practical Exam", 10),
            ("Voice Assistant", 11),
            ("Voice Notes", 12),
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

        # ---------------- PAGES STACK ----------------
        self.stack = QStackedWidget()
        self.code_runner_widget = CodeRunnerWidget()
        pages = (
            self._build_overview_page(), self._build_attendance_page(),
            AcademicTrackerWidget(self.user, role="student"),
            AssignmentsWidget(self.user, role="student"),
            NotesAndQuestionBankWidget(self.user, role="student"),
            NoticesAndRemindersWidget(self.user, role="student"),
            self._build_ai_tutor_page(), self.code_runner_widget,
            self._build_lab_manuals_page(), self._build_timetable_reminders_page(),
            self._build_lab_exam_page(),
            self._build_voice_assistant_page(), VoiceNotesWidget(self.user),
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

        student_name = self.user[3]
        header = create_section_header("Student Workspace", f"Welcome back, {student_name}")
        layout.addWidget(header)
        layout.addSpacing(16)

        stats = get_dashboard_stats_student(self.user[0])
        attendance_value = f"{stats['attendance_pct']}%" if stats["attendance_pct"] is not None else "—"
        attendance_description = (
            "Recorded attendance" if stats["attendance_records"] else "No attendance recorded yet"
        )
        academic_value = f"{stats['academic_average']}%" if stats["academic_average"] is not None else "—"
        lab_description = (
            f"{stats['completed_labs']} of {stats['total_labs']} experiments completed"
            if stats["total_labs"] else "No lab experiments available"
        )

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)
        cards_layout.addWidget(self._create_card("Overall Attendance", attendance_value, attendance_description, accent=True))
        cards_layout.addWidget(self._create_card("Pending Submissions", f"{stats['pending_assignments']}", "Assignments to Complete", primary=True))
        lab_value = f"{stats['lab_pct']}%" if stats["total_labs"] else "—"
        cards_layout.addWidget(self._create_card("Lab Practical Progress", lab_value, lab_description))
        cards_layout.addWidget(self._create_card("Academic Average", academic_value, "Published course marks"))

        layout.addLayout(cards_layout)
        layout.addSpacing(20)


        quick_header = create_section_header("Quick Access Portals")
        layout.addWidget(quick_header)
        layout.addSpacing(10)

        q_layout = QHBoxLayout()
        btn1 = QPushButton("Submit Assignments")
        style_action_button(btn1, "primary")
        btn1.setCursor(Qt.PointingHandCursor)
        btn1.clicked.connect(lambda: self.switch_page(3))

        btn2 = QPushButton("Notes && Question Bank")
        style_action_button(btn2, "primary")
        btn2.setCursor(Qt.PointingHandCursor)
        btn2.clicked.connect(lambda: self.switch_page(4))

        btn3 = QPushButton("Take Lab Practical Exam")
        style_action_button(btn3, "outline")
        btn3.setCursor(Qt.PointingHandCursor)
        btn3.clicked.connect(lambda: self.switch_page(10))

        q_layout.addWidget(btn1)
        q_layout.addWidget(btn2)
        q_layout.addWidget(btn3)
        layout.addLayout(q_layout)

        layout.addSpacing(16)

        # Download Transcript Card
        tr_card = QFrame()
        tr_card.setObjectName("surfaceCard")
        tr_card.setStyleSheet("""
            QFrame#surfaceCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        tr_layout = QVBoxLayout(tr_card)
        tr_lbl = QLabel("Official Academic Transcript & Attendance Summary")
        tr_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        tr_layout.addWidget(tr_lbl)

        btn_transcript = QPushButton("Download Academic && Attendance Transcript (HTML)")
        style_action_button(btn_transcript, "outline")
        btn_transcript.setCursor(Qt.PointingHandCursor)
        btn_transcript.clicked.connect(self._export_transcript)
        tr_layout.addWidget(btn_transcript)

        btn_transcript_xlsx = QPushButton("Download Academic && Attendance Workbook (Excel)")
        style_action_button(btn_transcript_xlsx, "outline")
        btn_transcript_xlsx.clicked.connect(self._export_transcript_xlsx)
        tr_layout.addWidget(btn_transcript_xlsx)

        layout.addWidget(tr_card)
        layout.addStretch()
        return page

    def _export_transcript(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Transcript", f"{self.user[3]}_Transcript.html", "HTML Files (*.html)")
        if fname:
            report_generator.export_student_transcript_html(self.user[0], fname)
            QMessageBox.information(self, "Success", f"Transcript saved successfully to:\n{fname}")

    def _export_transcript_xlsx(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Student Workbook", f"{self.user[3]}_Transcript.xlsx", "Excel Workbooks (*.xlsx)")
        if fname:
            try:
                if not report_generator.export_student_transcript_xlsx(self.user[0], fname):
                    raise ValueError("No student profile is linked to this account.")
                QMessageBox.information(self, "Success", f"Academic and attendance workbook saved to:\n{fname}")
            except Exception as error:
                QMessageBox.critical(self, "Could not export workbook", str(error))

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

        layout.addWidget(create_section_header("My Attendance Percentages"))
        layout.addSpacing(16)

        list_w = QListWidget()
        configure_wrapped_list(list_w)
        self.attendance_list = list_w
        summary = get_student_attendance(self.user[0])
        for code, name, total, present in summary:
            pct = round((present / total * 100), 1) if total > 0 else None
            result = f"{pct}%" if pct is not None else "No sessions recorded"
            list_w.addItem(f"{code} - {name}  |  Attended: {present}/{total} classes ({result})")

        layout.addWidget(list_w)
        layout.addSpacing(12)

        layout.addWidget(QLabel("Class QR check-in"))
        self.attendance_qr_input = QLineEdit()
        self.attendance_qr_input.setPlaceholderText("Paste the current 5-minute code shared by your faculty")
        qr_entry_row = QHBoxLayout()
        qr_entry_row.addWidget(self.attendance_qr_input, 1)
        qr_scan = QPushButton("Scan with Camera")
        qr_scan.setProperty("class", "outline")
        qr_scan.setToolTip("Scan the faculty's signed attendance QR locally; review and submit it afterwards.")
        qr_scan.clicked.connect(self._scan_attendance_qr)
        qr_entry_row.addWidget(qr_scan)
        layout.addLayout(qr_entry_row)
        qr_submit = QPushButton("Record attendance with code")
        qr_submit.setProperty("class", "secondary")
        qr_submit.clicked.connect(self._submit_attendance_qr)
        layout.addWidget(qr_submit)

        btn_tr = QPushButton("Export Personal Attendance Report")
        btn_tr.setCursor(Qt.PointingHandCursor)
        btn_tr.setProperty("class", "outline")
        btn_tr.clicked.connect(self._export_transcript)
        layout.addWidget(btn_tr)

        return page

    def _scan_attendance_qr(self):
        from PySide6.QtWidgets import QDialog
        from gui.qr_scanner import AttendanceQRScannerDialog

        scanner = AttendanceQRScannerDialog(self)
        if scanner.exec() == QDialog.Accepted and scanner.scanned_text:
            self.attendance_qr_input.setText(scanner.scanned_text)

    def _submit_attendance_qr(self):
        token = self.attendance_qr_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Attendance code", "Enter the code provided by your faculty.")
            return
        try:
            from attendance.qr_attendance import QRAttendanceSystem
            QRAttendanceSystem().record_attendance(self.user[0], token)
            self.attendance_qr_input.clear()
            QMessageBox.information(self, "Attendance", "Your attendance has been recorded.")
            self.attendance_list.clear()
            for code, name, total, present in get_student_attendance(self.user[0]):
                pct = round((present / total * 100), 1) if total else None
                result = f"{pct}%" if pct is not None else "No sessions recorded"
                self.attendance_list.addItem(f"{code} - {name}  |  Attended: {present}/{total} classes ({result})")
            self.switch_page(1)
        except Exception as error:
            QMessageBox.warning(self, "Attendance code", str(error))

    def _build_ai_tutor_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)

        layout.addWidget(create_section_header("AI Study Assistant & Local RAG", "Ask questions from uploaded course materials"))
        layout.addSpacing(12)

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask a question (e.g., 'Explain Unit 3', 'What is JVM?', 'What is Normalization?')...")

        ask_btn = QPushButton("Ask Assistant")
        ask_btn.setCursor(Qt.PointingHandCursor)
        ask_btn.setProperty("class", "secondary")
        ask_btn.clicked.connect(self._on_ask_tutor)

        layout.addWidget(self.query_input)
        layout.addWidget(ask_btn)
        layout.addSpacing(10)

        self.tutor_output = QTextEdit()
        self.tutor_output.setReadOnly(True)
        self.tutor_output.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                font-size: 13px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.tutor_output)

        return page

    def _on_ask_tutor(self):
        text = self.query_input.text().strip()
        if not text:
            return
        res = rag_engine.query(text, role="student")
        self.tutor_output.setPlainText(f"Answer:\n{res['answer']}\n\n[Source: {res['source']}]")

    def _build_lab_manuals_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)

        layout.addWidget(create_section_header("Lab Experiments & Reference Manuals"))
        layout.addSpacing(12)

        self.lab_progress_table = QTableWidget(0, 3)
        self.lab_progress_table.setHorizontalHeaderLabels(["Course", "Experiment", "Progress"])
        self.lab_progress_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lab_progress_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lab_progress_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lab_progress_table.itemSelectionChanged.connect(self._show_lab_experiment)
        layout.addWidget(self.lab_progress_table)
        self.lab_description = QLabel("Select an experiment to view its instructions.")
        self.lab_description.setWordWrap(True)
        layout.addWidget(self.lab_description)
        self.lab_work_input = QTextEdit()
        self.lab_work_input.setPlaceholderText("Describe your solution or paste a short work summary for faculty review.")
        self.lab_work_input.setMinimumHeight(110)
        layout.addWidget(self.lab_work_input)
        self.lab_submit_button = QPushButton("Submit Lab Work for Review")
        self.lab_submit_button.setEnabled(False)
        self.lab_submit_button.clicked.connect(self._submit_lab_work)
        layout.addWidget(self.lab_submit_button)
        self._refresh_lab_progress()
        return page

    def _refresh_lab_progress(self):
        self.lab_progress_rows = get_student_lab_progress(self.user[0])
        self.lab_progress_table.clearSpans()
        self.lab_progress_table.setRowCount(len(self.lab_progress_rows))
        for index, row in enumerate(self.lab_progress_rows):
            experiment_id, code, subject, number, title, description, status, notes = row
            for col, value in enumerate((f"{code} — {subject}", f"#{number}: {title}", status)):
                self.lab_progress_table.setItem(index, col, QTableWidgetItem(str(value)))
        if not self.lab_progress_rows:
            self.lab_progress_table.setRowCount(1)
            self.lab_progress_table.setSpan(0, 0, 1, 3)
            self.lab_progress_table.setItem(0, 0, QTableWidgetItem("No lab experiments have been published."))
        self.lab_work_input.clear()
        self.lab_work_input.setReadOnly(False)
        self.lab_submit_button.setEnabled(False)

    def _show_lab_experiment(self):
        row = self.lab_progress_table.currentRow()
        if 0 <= row < len(getattr(self, "lab_progress_rows", [])):
            experiment = self.lab_progress_rows[row]
            self.lab_description.setText(f"{experiment[1]} — {experiment[4]}\n\n{experiment[5] or 'No instructions have been added.'}\n\nStatus: {experiment[6]}")
            self.lab_work_input.setPlainText(experiment[7])
            self.lab_work_input.setReadOnly(experiment[6] == "Completed")
            self.lab_submit_button.setEnabled(experiment[6] != "Completed")

    def _submit_lab_work(self):
        row = self.lab_progress_table.currentRow()
        if not 0 <= row < len(getattr(self, "lab_progress_rows", [])):
            QMessageBox.information(self, "Lab work", "Select an experiment first.")
            return
        try:
            submit_lab_experiment(self.lab_progress_rows[row][0], self.user[0], self.lab_work_input.toPlainText())
            QMessageBox.information(self, "Submitted", "Your work was sent to faculty for review.")
            self._refresh_lab_progress()
        except Exception as error:
            QMessageBox.warning(self, "Could not submit lab work", str(error))

    def _build_timetable_reminders_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)

        layout.addWidget(create_section_header("Class Schedule & Academic Reminders"))
        layout.addSpacing(12)

        list_w = QListWidget()
        configure_wrapped_list(list_w)
        tt = get_timetables()
        for t in tt:
            list_w.addItem(f"{t[3]} | {t[4]} - {t[5]} | {t[1]} ({t[2]}) in {t[6]}")

        rems = get_reminders(self.user[0])
        for r in rems:
            list_w.addItem(f"Reminder [{r[2]}]: {r[1]} (Due: {r[3]})")

        layout.addWidget(list_w)
        return page

    def _build_lab_exam_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)

        layout.addWidget(create_section_header("Lab Practical Exam Module"))
        layout.addSpacing(12)

        exam_data = lab_exam_assistant.get_active_exam()
        if not exam_data:
            empty = QLabel("There is no active practical exam right now. Your faculty will publish the exam here when it is ready.")
            empty.setWordWrap(True)
            empty.setObjectName("surfaceCard")
            layout.addWidget(empty)
            return page
        
        ex_card = QFrame()
        ex_card.setObjectName("surfaceCard")
        ex_card.setStyleSheet("""
            QFrame#surfaceCard {
                background-color: rgba(72, 103, 125, 0.04);
                border: 1px solid rgba(72, 103, 125, 0.12);
                border-radius: 8px;
                padding: 12px;
            }
            QLabel {
                color: #48677D;
                font-size: 14px;
                font-weight: 700;
            }
        """)
        ex_layout = QVBoxLayout(ex_card)
        ex_info = QLabel(f"Active Exam: {exam_data['title']} ({exam_data['subject_code']}) | Duration: {exam_data['duration_minutes']} Minutes")
        ex_layout.addWidget(ex_info)

        layout.addWidget(ex_card)
        layout.addSpacing(10)

        self.active_exam_data = exam_data
        self.exam_clock_label = QLabel("Start the exam when you are ready. The timer begins after confirmation.")
        layout.addWidget(self.exam_clock_label)
        self.exam_start_button = QPushButton("Start / Resume Exam")
        self.exam_start_button.clicked.connect(self._start_lab_exam)
        layout.addWidget(self.exam_start_button)

        q_paper = QTextEdit()
        q_paper.setReadOnly(True)
        q_paper.setPlainText(exam_data['question_paper'])
        q_paper.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                font-size: 13px;
            }
        """)
        layout.addWidget(q_paper)

        sol_lbl = QLabel("Practical Solution Code:")
        sol_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #0F172A;")
        layout.addWidget(sol_lbl)

        self.exam_solution = QTextEdit()
        self.exam_solution.setEnabled(False)
        self.exam_solution.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #26323B;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                border: 1px solid #DCE2E7;
                border-radius: 8px;
            }
        """)
        layout.addWidget(self.exam_solution)

        sub_btn = QPushButton("Submit Exam Solution")
        sub_btn.setCursor(Qt.PointingHandCursor)
        sub_btn.setProperty("class", "secondary")
        sub_btn.setEnabled(False)
        self.exam_submit_button = sub_btn
        sub_btn.clicked.connect(self._submit_exam)
        layout.addWidget(sub_btn)

        self.exam_timer = QTimer(self)
        self.exam_timer.timeout.connect(self._update_exam_timer)
        self.exam_seconds_remaining = 0

        return page

    def _start_lab_exam(self):
        try:
            remaining = lab_exam_assistant.start_exam(self.active_exam_data["id"], self.user[0])
            self.exam_seconds_remaining = remaining
            self.exam_solution.setEnabled(True)
            self.exam_submit_button.setEnabled(True)
            self.exam_start_button.setEnabled(False)
            self.exam_timer.start(1000)
            self._update_exam_timer()
        except Exception as error:
            self.exam_clock_label.setText(str(error))
            self.exam_start_button.setEnabled(False)

    def _update_exam_timer(self):
        if self.exam_seconds_remaining <= 0:
            self.exam_timer.stop()
            self.exam_clock_label.setText("Time expired. The solution can no longer be submitted.")
            self.exam_solution.setEnabled(False)
            self.exam_submit_button.setEnabled(False)
            return
        minutes, seconds = divmod(self.exam_seconds_remaining, 60)
        self.exam_clock_label.setText(f"Time remaining: {minutes:02d}:{seconds:02d}")
        self.exam_seconds_remaining -= 1

    def _build_voice_assistant_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(create_section_header("Voice Command Console", "Type a phrase to use offline course and reminder commands"))
        self.voice_command_input = QLineEdit()
        self.voice_command_input.setPlaceholderText("Try: read schedule, read reminders, or ask a course question")
        run_button = QPushButton("Process command")
        run_button.setProperty("class", "secondary")
        run_button.clicked.connect(self._run_student_voice_command)
        layout.addWidget(self.voice_command_input)
        layout.addWidget(run_button)
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
        self.voice_command_output = QTextEdit()
        self.voice_command_output.setReadOnly(True)
        layout.addWidget(self.voice_command_output, 1)
        return page

    def _run_student_voice_command(self):
        text = self.voice_command_input.text().strip()
        if not text:
            return
        intent = voice_engine.process_command(text)
        if intent.get("intent") == "launch_app":
            choice = QMessageBox.question(self, "Confirm application launch", intent["reply"],
                                          QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if choice == QMessageBox.Yes:
                try:
                    result = voice_engine.launch_confirmed_app(intent["executable"], intent["app"])
                except Exception as error:
                    result = str(error)
            else:
                result = "Application launch cancelled."
        elif intent.get("intent") == "start_timer" and intent.get("status") == "success":
            self.voice_seconds_remaining = intent["duration_seconds"]
            self.voice_timer.start(1000)
            self.voice_timer_cancel.setEnabled(True)
            self._tick_voice_timer()
            result = intent["reply"]
        elif intent.get("intent") == "start_timer":
            result = intent.get("reply", "The timer could not be started.")
        elif intent.get("intent") in {"run_python", "compile_java"}:
            language = "Python" if intent["intent"] == "run_python" else "Java"
            self.code_runner_widget.lang_combo.setCurrentText(language)
            self.switch_page(7)
            self.code_runner_widget.output_edit.setPlainText(
                f"{language} sample loaded. No code has been run. Review the source and choose Run Code to confirm isolated execution."
            )
            result = (f"{language} code runner opened with a sample program. Review the code and choose Run Code "
                      "to confirm isolated execution.")
        elif intent.get("intent") == "create_project":
            self.switch_page(7)
            self.code_runner_widget.output_edit.setPlainText(
                "No project has been created. Choose New Project to set its name, language, and parent folder."
            )
            result = "Code Runner opened. Choose New Project and confirm the destination to create starter files."
        else:
            result = execute_voice_intent(intent, user_id=self.user[0], role="student")
        self.voice_command_output.append(f"> {text}\n[Assistant]: {result}\n")
        self.voice_command_input.clear()

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
        self.voice_command_input.setText(phrase)
        self._run_student_voice_command()

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
            voice_engine.speak("Your study timer is complete.")
            return
        self.voice_seconds_remaining -= 1

    def _cancel_voice_timer(self):
        self.voice_timer.stop()
        self.voice_seconds_remaining = 0
        self.voice_timer_label.setText("Timer cancelled")
        self.voice_timer_cancel.setEnabled(False)

    def _submit_exam(self):
        code = self.exam_solution.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Warning", "Please write your exam solution before submitting.")
            return
        exam_data = getattr(self, "active_exam_data", None)
        if not exam_data:
            QMessageBox.warning(self, "Exam unavailable", "There is no active exam to submit to.")
            return
        try:
            lab_exam_assistant.submit_exam(exam_data["id"], self.user[0], code)
            QMessageBox.information(self, "Submitted", "Your solution was saved. Faculty evaluation is pending.")
            self.exam_solution.clear()
            self.exam_solution.setEnabled(False)
            self.exam_submit_button.setEnabled(False)
            self.exam_timer.stop()
            self.exam_clock_label.setText("Submitted. Faculty evaluation is pending.")
        except Exception as error:
            QMessageBox.critical(self, "Submission failed", str(error))

    def logout(self):
        self.close()
        self.logout_callback()
