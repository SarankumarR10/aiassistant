from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QStackedWidget, QTextEdit,
    QLineEdit, QListWidget, QFileDialog
)
from PySide6.QtCore import Qt
from gui.student_attendance import StudentAttendanceWindow
from gui.code_runner_widget import CodeRunnerWidget
from gui.assignments_widget import AssignmentsWidget
from gui.notes_qbank_widget import NotesAndQuestionBankWidget
from gui.notices_widget import NoticesAndRemindersWidget
from reports.report_generator import report_generator
from ai.rag_engine import rag_engine
from voice.voice_engine import voice_engine
from voice.commands import execute_voice_intent
from lab.lab_exam import lab_exam_assistant
from database.database import get_student_attendance, get_timetables, get_lab_experiments, get_reminders

class StudentDashboard(QMainWindow):

    def __init__(self, user, logout_callback):
        super().__init__()
        self.user = user
        self.logout_callback = logout_callback

        self.setWindowTitle("EduPilot / VCET Assistant - Student Workspace")
        self.resize(1280, 800)

        self.build_ui()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame { background-color: #0B1220; }
            QLabel { color: white; }
            QPushButton {
                background-color: transparent;
                color: #CBD5E1;
                border: none;
                padding: 11px 14px;
                text-align: left;
                font-size: 13px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #172033; color: white; }
            QPushButton:checked { background-color: #2563EB; color: white; font-weight: bold; }
        """)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)

        logo = QLabel("EDUPILOT")
        logo.setStyleSheet("font-size: 22px; font-weight: bold; color: #60A5FA;")
        subtitle = QLabel("Student Learning Portal")
        subtitle.setStyleSheet("color: #64748B; font-size: 12px;")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(15)

        nav_items = [
            ("Dashboard", 0),
            ("My Attendance %", 1),
            ("My Assignments", 2),
            ("Notes & Question Bank", 3),
            ("Class Notices & Reminders", 4),
            ("AI Study Tutor & RAG", 5),
            ("Code Execution Sandbox", 6),
            ("Lab Manuals & Progress", 7),
            ("Timetable & Schedule", 8),
            ("Lab Exam Assistant", 9),
        ]

        self.nav_buttons = []
        for text, page_idx in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, idx=page_idx: self.switch_page(idx))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sidebar_layout.addStretch()

        logout_button = QPushButton("Logout")
        logout_button.clicked.connect(self.logout)
        sidebar_layout.addWidget(logout_button)

        # Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_overview_page())
        self.stack.addWidget(self._build_attendance_page())
        self.stack.addWidget(AssignmentsWidget(self.user, role="student"))
        self.stack.addWidget(NotesAndQuestionBankWidget(self.user, role="student"))
        self.stack.addWidget(NoticesAndRemindersWidget(self.user, role="student"))
        self.stack.addWidget(self._build_ai_tutor_page())
        self.stack.addWidget(CodeRunnerWidget())
        self.stack.addWidget(self._build_lab_manuals_page())
        self.stack.addWidget(self._build_timetable_reminders_page())
        self.stack.addWidget(self._build_lab_exam_page())

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        self.switch_page(0)

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #0F172A; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        student_name = self.user[3]
        welcome = QLabel(f"Welcome back, {student_name}")
        welcome.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(welcome)
        layout.addSpacing(15)

        cards_layout = QHBoxLayout()
        cards_layout.addWidget(self._create_card("Overall Attendance", "88%", "Eligible for Exams", "#10B981"))
        cards_layout.addWidget(self._create_card("Current CGPA", "8.4", "Rank #5 in Class", "#3B82F6"))
        cards_layout.addWidget(self._create_card("Lab Progress", "75%", "3 of 4 Experiments Done", "#8B5CF6"))
        cards_layout.addWidget(self._create_card("Pending Tasks", "2", "Due this Friday", "#F59E0B"))

        layout.addLayout(cards_layout)
        layout.addSpacing(25)

        quick_label = QLabel("Quick Access Tools")
        quick_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(quick_label)

        q_layout = QHBoxLayout()
        btn1 = QPushButton("Submit Assignments")
        btn1.setStyleSheet("background-color: rgba(37, 99, 235, 0.3); border: 1px solid rgba(37, 99, 235, 0.5); color: #60A5FA; padding: 12px; font-weight: bold; border-radius: 8px;")
        btn1.clicked.connect(lambda: self.switch_page(2))

        btn2 = QPushButton("Browse Notes & Question Bank")
        btn2.setStyleSheet("background-color: rgba(16, 185, 129, 0.3); border: 1px solid rgba(16, 185, 129, 0.5); color: #34D399; padding: 12px; font-weight: bold; border-radius: 8px;")
        btn2.clicked.connect(lambda: self.switch_page(3))

        btn3 = QPushButton("Take Lab Practical Exam")
        btn3.setStyleSheet("background-color: rgba(245, 158, 11, 0.3); border: 1px solid rgba(245, 158, 11, 0.5); color: #FBBF24; padding: 12px; font-weight: bold; border-radius: 8px;")
        btn3.clicked.connect(lambda: self.switch_page(9))

        q_layout.addWidget(btn1)
        q_layout.addWidget(btn2)
        q_layout.addWidget(btn3)
        layout.addLayout(q_layout)

        layout.addSpacing(15)

        btn_transcript = QPushButton(" Download Academic & Attendance Transcript (HTML)")
        btn_transcript.setStyleSheet("background-color: #1F2937; color: #60A5FA; padding: 10px 14px; font-weight: bold; border: 1px solid #2563EB; border-radius: 6px;")
        btn_transcript.clicked.connect(self._export_transcript)
        layout.addWidget(btn_transcript)

        layout.addStretch()
        return page

    def _export_transcript(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Transcript", f"{self.user[3]}_Transcript.html", "HTML Files (*.html)")
        if fname:
            report_generator.export_student_transcript_html(self.user[0], fname)
            QMessageBox.information(self, "Success", f"Transcript saved successfully to:\n{fname}")

    def _create_card(self, title, val, desc, color):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #1F2937; border-left: 4px solid {color}; border-radius: 8px; padding: 12px;")
        v = QVBoxLayout(frame)
        t = QLabel(title)
        t.setStyleSheet("color: #94A3B8; font-size: 12px;")
        v_lbl = QLabel(val)
        v_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        d = QLabel(desc)
        d.setStyleSheet("color: #64748B; font-size: 11px;")
        v.addWidget(t)
        v.addWidget(v_lbl)
        v.addWidget(d)
        return frame

    def _build_attendance_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #111827; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        title = QLabel("My Subject-Wise Attendance Record")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #10B981;")
        layout.addWidget(title)

        list_w = QListWidget()
        list_w.setStyleSheet("background-color: #1F2937; color: #E5E7EB; font-size: 14px; padding: 10px;")

        summary = get_student_attendance(self.user[0])
        for code, name, total, present in summary:
            pct = round((present / total * 100), 1) if total > 0 else 100.0
            list_w.addItem(f"{code} - {name} | Attended: {present}/{total} classes ({pct}%)")

        layout.addWidget(list_w)

        btn_tr = QPushButton(" Export Personal Attendance Report")
        btn_tr.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_tr.clicked.connect(self._export_transcript)
        layout.addWidget(btn_tr)

        return page

    def _build_ai_tutor_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #0F172A; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("AI Study Assistant & Offline RAG Document Q&A")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(title)

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask 'Explain Unit 3', 'What is JVM?', 'What is Normalization?'...")
        self.query_input.setStyleSheet("background-color: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); color: white; padding: 10px; font-size: 14px; border-radius: 8px;")

        ask_btn = QPushButton("Ask Assistant")
        ask_btn.setStyleSheet("background-color: rgba(37, 99, 235, 0.8); color: white; font-weight: bold; padding: 10px; border-radius: 8px;")
        ask_btn.clicked.connect(self._on_ask_tutor)

        layout.addWidget(self.query_input)
        layout.addWidget(ask_btn)

        self.tutor_output = QTextEdit()
        self.tutor_output.setReadOnly(True)
        self.tutor_output.setStyleSheet("background-color: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.08); color: #E5E7EB; font-size: 13px; border-radius: 8px;")
        layout.addWidget(self.tutor_output)

        return page

    def _on_ask_tutor(self):
        text = self.query_input.text().strip()
        if not text:
            return
        res = rag_engine.query(text)
        self.tutor_output.setPlainText(f"Answer:\n{res['answer']}\n\n[Source: {res['source']}]")

    def _build_lab_manuals_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #0F172A; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("Lab Experiments & Lab Manuals")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #8B5CF6;")
        layout.addWidget(title)

        list_w = QListWidget()
        list_w.setStyleSheet("background-color: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.08); color: #E5E7EB; font-size: 13px; padding: 8px; border-radius: 8px;")
        
        exps = get_lab_experiments()
        for e in exps:
            list_w.addItem(f"Exp #{e[3]} [{e[1]} - {e[2]}]: {e[4]}\n   Description: {e[5]}")

        layout.addWidget(list_w)
        return page

    def _build_timetable_reminders_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #0F172A; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("Class Schedule & Voice Reminders")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F59E0B;")
        layout.addWidget(title)

        list_w = QListWidget()
        list_w.setStyleSheet("background-color: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.08); color: #E5E7EB; font-size: 13px; padding: 8px; border-radius: 8px;")
        
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
        page.setStyleSheet("background-color: #111827; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("Lab Examination Assistant")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #EF4444;")
        layout.addWidget(title)

        exam_data = lab_exam_assistant.get_active_exam()
        
        ex_info = QLabel(f"Active Exam: {exam_data['title']} ({exam_data['subject_code']}) | Time Limit: {exam_data['duration_minutes']} Mins")
        ex_info.setStyleSheet("font-size: 15px; font-weight: bold; color: #FCA5A5;")
        layout.addWidget(ex_info)

        q_paper = QTextEdit()
        q_paper.setReadOnly(True)
        q_paper.setPlainText(exam_data['question_paper'])
        q_paper.setStyleSheet("background-color: #1F2937; color: #FEE2E2; font-size: 13px;")
        layout.addWidget(q_paper)

        sol_lbl = QLabel("Your Solution Code:")
        layout.addWidget(sol_lbl)

        self.exam_solution = QTextEdit()
        self.exam_solution.setStyleSheet("background-color: #12121c; color: #00ffcc; font-family: Consolas; font-size: 13px;")
        layout.addWidget(self.exam_solution)

        sub_btn = QPushButton("Submit Exam Solution")
        sub_btn.setStyleSheet("background-color: #DC2626; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        sub_btn.clicked.connect(self._submit_exam)
        layout.addWidget(sub_btn)

        return page

    def _submit_exam(self):
        code = self.exam_solution.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Warning", "Please write your exam solution before submitting.")
            return
        QMessageBox.information(self, "Submitted", "Lab Exam Solution submitted successfully! Evaluation pending.")
        self.exam_solution.clear()

    def logout(self):
        self.close()
        self.logout_callback()