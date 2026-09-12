from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QStackedWidget, QTextEdit,
    QLineEdit, QListWidget, QFileDialog
)
from PySide6.QtCore import Qt
from gui.attendance import AttendanceWindow
from gui.analytics_widget import ClassroomAnalyticsWidget
from gui.code_runner_widget import CodeRunnerWidget
from gui.lab_monitor_widget import LabMonitorWidget
from gui.assignments_widget import AssignmentsWidget
from gui.notes_qbank_widget import NotesAndQuestionBankWidget
from gui.notices_widget import NoticesAndRemindersWidget
from reports.report_generator import report_generator
from ai.rag_engine import rag_engine
from voice.voice_engine import voice_engine
from voice.commands import execute_voice_intent
from database.database import get_timetables, get_assignments, get_notes, add_announcement

class FacultyDashboard(QMainWindow):

    def __init__(self, user, logout_callback):
        super().__init__()
        self.user = user
        self.logout_callback = logout_callback

        self.setWindowTitle("EduPilot / VCET Assistant - Faculty Workspace")
        self.resize(1280, 800)

        self.build_ui()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------- SIDEBAR ----------------
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
            QPushButton:hover {
                background-color: #172033;
                color: white;
            }
            QPushButton:checked {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
            }
        """)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)

        logo = QLabel("EDUPILOT")
        logo.setStyleSheet("font-size: 22px; font-weight: bold; color: #60A5FA;")
        subtitle = QLabel("VCET Faculty Assistant")
        subtitle.setStyleSheet("color: #64748B; font-size: 12px;")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(15)

        nav_items = [
            ("Dashboard", 0),
            ("Smart Attendance & Reports", 1),
            ("Classroom Analytics", 2),
            ("Assignments & Grading", 3),
            ("Notes & Question Bank", 4),
            ("Notices & Reminders", 5),
            ("Lab Monitor & Health", 6),
            ("Offline Code Sandbox", 7),
            ("AI Tutor & RAG", 8),
            ("Timetable & Schedule", 9),
            ("Voice & Classroom", 10),
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

        # ---------------- STACKED PAGES ----------------
        self.stack = QStackedWidget()

        # Page 0: Main Overview Dashboard
        self.stack.addWidget(self._build_overview_page())
        # Page 1: Attendance Launcher
        self.stack.addWidget(self._build_attendance_page())
        # Page 2: Analytics Widget
        self.stack.addWidget(ClassroomAnalyticsWidget())
        # Page 3: Assignments & Grading Widget
        self.stack.addWidget(AssignmentsWidget(self.user, role="faculty"))
        # Page 4: Notes & Question Bank Widget
        self.stack.addWidget(NotesAndQuestionBankWidget(self.user, role="faculty"))
        # Page 5: Notices & Reminders Widget
        self.stack.addWidget(NoticesAndRemindersWidget(self.user, role="faculty"))
        # Page 6: Lab Monitor Widget
        self.stack.addWidget(LabMonitorWidget())
        # Page 7: Code Runner Widget
        self.stack.addWidget(CodeRunnerWidget())
        # Page 8: AI RAG & Tutor Page
        self.stack.addWidget(self._build_ai_rag_page())
        # Page 9: Timetable Page
        self.stack.addWidget(self._build_timetable_page())
        # Page 10: Voice Assistant Page
        self.stack.addWidget(self._build_voice_page())

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        self.switch_page(0)

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #111827; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        header = QLabel(f"Welcome back, {self.user[3]}")
        header.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(header)
        layout.addSpacing(15)

        cards_layout = QHBoxLayout()
        cards_layout.addWidget(self._create_card("Total Students", "42", "CSE-C Section", "#3B82F6"))
        cards_layout.addWidget(self._create_card("Today's Attendance", "87%", "Present in Lab", "#10B981"))
        cards_layout.addWidget(self._create_card("Workstation Status", "Healthy", "All 30 PCs Operational", "#8B5CF6"))
        cards_layout.addWidget(self._create_card("Voice Assistant", "Active", "'Hey VCET Assistant'", "#F59E0B"))

        layout.addLayout(cards_layout)
        layout.addSpacing(25)

        quick_label = QLabel("Quick Launcher & Export Engine")
        quick_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(quick_label)

        q_layout = QHBoxLayout()
        btn1 = QPushButton("Start Smart Attendance Taker")
        btn1.setStyleSheet("background-color: #2563EB; color: white; padding: 10px; font-weight: bold; border-radius: 6px;")
        btn1.clicked.connect(lambda: self.switch_page(1))
        
        btn2 = QPushButton("Assignments & Grading Workspace")
        btn2.setStyleSheet("background-color: #059669; color: white; padding: 10px; font-weight: bold; border-radius: 6px;")
        btn2.clicked.connect(lambda: self.switch_page(3))

        btn3 = QPushButton("Notes & Question Bank Manager")
        btn3.setStyleSheet("background-color: #7C3AED; color: white; padding: 10px; font-weight: bold; border-radius: 6px;")
        btn3.clicked.connect(lambda: self.switch_page(4))

        q_layout.addWidget(btn1)
        q_layout.addWidget(btn2)
        q_layout.addWidget(btn3)
        layout.addLayout(q_layout)

        layout.addSpacing(15)
        
        # Export Actions Bar
        export_layout = QHBoxLayout()
        btn_exp_csv = QPushButton(" Export Attendance CSV")
        btn_exp_csv.setStyleSheet("background-color: #374151; color: #34D399; padding: 8px 12px; font-weight: bold; border-radius: 6px; border: 1px solid #059669;")
        btn_exp_csv.clicked.connect(self._export_attendance_csv)

        btn_exp_html = QPushButton(" Export Printable PDF/HTML Report")
        btn_exp_html.setStyleSheet("background-color: #374151; color: #60A5FA; padding: 8px 12px; font-weight: bold; border-radius: 6px; border: 1px solid #2563EB;")
        btn_exp_html.clicked.connect(self._export_attendance_html)

        export_layout.addWidget(btn_exp_csv)
        export_layout.addWidget(btn_exp_html)
        export_layout.addStretch()

        layout.addLayout(export_layout)
        layout.addStretch()

        return page

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

        title = QLabel("Smart Attendance System (Face / QR / Voice)")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #3498db;")
        layout.addWidget(title)

        desc = QLabel("Mark session attendance using camera-based Face Recognition with anti-proxy check, dynamic QR scanning, or manual entry.")
        desc.setStyleSheet("color: #94A3B8; font-size: 13px;")
        layout.addWidget(desc)
        layout.addSpacing(20)

        launch_btn = QPushButton(" Launch Attendance Taker Window")
        launch_btn.setStyleSheet("background-color: #2563EB; color: white; font-size: 16px; padding: 14px; font-weight: bold; border-radius: 8px;")
        launch_btn.clicked.connect(self._open_attendance_window)
        layout.addWidget(launch_btn)

        layout.addSpacing(20)

        rep_lbl = QLabel("Report Exports")
        rep_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(rep_lbl)

        h = QHBoxLayout()
        b1 = QPushButton("Export Class Attendance Spreadsheet (CSV)")
        b1.setStyleSheet("background-color: #1F2937; color: #34D399; padding: 10px; font-weight: bold; border: 1px solid #059669; border-radius: 6px;")
        b1.clicked.connect(self._export_attendance_csv)

        b2 = QPushButton("Export Printable Attendance Summary (HTML/PDF)")
        b2.setStyleSheet("background-color: #1F2937; color: #60A5FA; padding: 10px; font-weight: bold; border: 1px solid #2563EB; border-radius: 6px;")
        b2.clicked.connect(self._export_attendance_html)

        h.addWidget(b1)
        h.addWidget(b2)
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
            QMessageBox.information(self, "Success", f"Attendance HTML/PDF printable report saved to:\n{fname}")

    def _open_attendance_window(self):
        self.att_win = AttendanceWindow(self.user[0])
        self.att_win.show()

    def _build_ai_rag_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #111827; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("Offline Document Q&A / RAG Assistant")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F59E0B;")
        layout.addWidget(title)

        self.rag_input = QLineEdit()
        self.rag_input.setPlaceholderText("Ask a question (e.g. 'Explain Unit 3', 'What is JVM?', 'What is Normalization?')...")
        self.rag_input.setStyleSheet("background-color: #1F2937; color: white; padding: 10px; font-size: 14px; border: 1px solid #374151; border-radius: 6px;")
        
        ask_btn = QPushButton("Search Local Documents & FAQs")
        ask_btn.setStyleSheet("background-color: #D97706; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        ask_btn.clicked.connect(self._on_ask_rag)

        layout.addWidget(self.rag_input)
        layout.addWidget(ask_btn)

        self.rag_output = QTextEdit()
        self.rag_output.setReadOnly(True)
        self.rag_output.setStyleSheet("background-color: #1F2937; color: #E5E7EB; font-size: 13px; border: 1px solid #374151;")
        layout.addWidget(self.rag_output)

        return page

    def _on_ask_rag(self):
        query = self.rag_input.text().strip()
        if not query:
            return
        res = rag_engine.query(query)
        self.rag_output.setPlainText(f"Answer: {res['answer']}\n\n[Source: {res['source']} | Confidence: {res['confidence']}]")

    def _build_timetable_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #111827; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("Faculty Schedule & Timetable")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #3B82F6;")
        layout.addWidget(title)

        list_w = QListWidget()
        list_w.setStyleSheet("background-color: #1F2937; color: #E5E7EB; font-size: 14px; padding: 10px;")
        
        rows = get_timetables()
        for r in rows:
            list_w.addItem(f"{r[3]} | {r[4]} - {r[5]} | Subject: {r[1]} ({r[2]}) | Room: {r[6]}")

        layout.addWidget(list_w)
        return page

    def _build_voice_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #111827; color: white;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)

        title = QLabel("Offline Voice Assistant & Classroom Controls")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #10B981;")
        layout.addWidget(title)

        sub = QLabel("Supports wake-word 'Hey VCET Assistant' and commands like 'Open VS Code', 'Next slide', 'Read schedule', 'Read announcements'.")
        sub.setStyleSheet("color: #94A3B8;")
        layout.addWidget(sub)

        self.voice_cmd_input = QLineEdit()
        self.voice_cmd_input.setPlaceholderText("Type or speak voice command (e.g. 'Hey VCET Assistant open VS Code')...")
        self.voice_cmd_input.setStyleSheet("background-color: #1F2937; color: white; padding: 10px; font-size: 14px;")

        send_voice_btn = QPushButton(" Execute Voice Command")
        send_voice_btn.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        send_voice_btn.clicked.connect(self._on_voice_cmd)

        layout.addWidget(self.voice_cmd_input)
        layout.addWidget(send_voice_btn)

        self.voice_log = QTextEdit()
        self.voice_log.setReadOnly(True)
        self.voice_log.setStyleSheet("background-color: #1F2937; color: #10B981; font-family: Consolas, monospace; font-size: 13px;")
        layout.addWidget(self.voice_log)

        return page

    def _on_voice_cmd(self):
        text = self.voice_cmd_input.text().strip()
        if not text:
            return
        intent = voice_engine.process_command(text)
        res = execute_voice_intent(intent)
        self.voice_log.append(f"> {text}\n[Assistant]: {res}\n")
        self.voice_cmd_input.clear()

    def logout(self):
        self.close()
        self.logout_callback()