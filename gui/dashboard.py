from pathlib import Path

from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QFrame, QLabel, QMainWindow, QMessageBox, QPushButton

from gui.dialogs import AttendanceTakerDialog, LabAssistantDialog, StudentDirectoryDialog


FACULTY_MODULES = {
    "dashboard": {
        "navigation": "Faculty Dashboard",
        "title": "Good morning, Faculty!",
        "subtitle": "EduPilot keeps your classroom and lab day organised.",
        "metrics": (
            ("TODAY'S CLASSES", "08", "2 begin in the next hour"),
            ("STUDENTS PRESENT", "54", "90% attendance rate"),
            ("LAB SYSTEMS READY", "42", "All critical systems online"),
            ("PENDING REVIEWS", "05", "Assignments awaiting review"),
        ),
        "assistant": ("EduPilot is ready to assist", "Try: mark attendance, open Lab 2, or show at-risk learners."),
        "activity": (("Attendance ready for III CSE - A", "Today, 09:45 AM"), ("Java Lab 2 startup check completed", "Today, 08:50 AM")),
        "status": "Ready for faculty commands",
        "action": "voice",
        "action_label": "Start Listening",
    },
    "students": {
        "navigation": "Student Management",
        "title": "Student Management",
        "subtitle": "Maintain student details and quickly access individual academic records.",
        "metrics": (("TOTAL STUDENTS", "60", "Across assigned sections"), ("NEW ENTRIES", "04", "Added this month"), ("AT-RISK STUDENTS", "04", "Needs faculty review"), ("PROFILE UPDATES", "03", "Awaiting confirmation")),
        "assistant": ("Student workspace is ready", "Search a student or open a profile to view attendance and academic details."),
        "activity": (("Student profile verified: S. Karthik", "Today, 09:10 AM"), ("New student added to III CSE - A", "Yesterday, 04:20 PM")),
        "status": "Student records available",
        "action": "students",
        "action_label": "Open Student Management",
    },
    "attendance": {
        "navigation": "Attendance Taker",
        "title": "Attendance Taker",
        "subtitle": "Record attendance for the current class and identify defaulters early.",
        "metrics": (("PRESENT TODAY", "54", "90% overall attendance"), ("ABSENT TODAY", "06", "2 need a follow-up"), ("SECTIONS COMPLETE", "03/04", "One register still open"), ("AT-RISK STUDENTS", "04", "Below 75% attendance")),
        "assistant": ("Attendance workflow is ready", "Open the register to mark each student present or absent."),
        "activity": (("III CSE - A attendance marked by faculty", "Today, 09:45 AM"), ("Attendance alert prepared for two students", "Yesterday, 04:18 PM")),
        "status": "Attendance register ready",
        "action": "attendance",
        "action_label": "Open Attendance Taker",
    },
    "academics": {
        "navigation": "Academic Tracker",
        "title": "Academic Tracker",
        "subtitle": "Monitor marks, assignments, lab completion, and students needing support.",
        "metrics": (("CLASS AVERAGE", "78%", "Up 3% from last assessment"), ("ASSIGNMENTS DUE", "12", "Due this week"), ("AT-RISK LEARNERS", "04", "Needs faculty review"), ("LAB COMPLETION", "75%", "Across current experiments")),
        "assistant": ("Academic tracking is ready", "Review learner progress, pending work, and assessment performance."),
        "activity": (("Internal marks imported for Data Structures", "Today, 09:05 AM"), ("Assignment reminder queued for III CSE - B", "Yesterday, 05:20 PM")),
        "status": "Academic data ready for review",
        "action": "info",
        "action_label": "View Academic Summary",
    },
    "labs": {
        "navigation": "Lab Assistant",
        "title": "Lab Assistant",
        "subtitle": "Run today's experiment, open development tools, and monitor laboratory readiness.",
        "metrics": (("LABS AVAILABLE", "03", "All scheduled labs open"), ("SYSTEMS ONLINE", "42/44", "2 systems need attention"), ("EXPERIMENTS TODAY", "06", "Across three laboratories"), ("SAFETY CHECKS", "100%", "All checks completed")),
        "assistant": ("Your lab assistant is ready", "Open VS Code, review today's experiment, or check system readiness."),
        "activity": (("Python Lab system health check completed", "Today, 08:50 AM"), ("Two systems flagged for maintenance", "Today, 08:42 AM")),
        "status": "Lab monitoring is active",
        "action": "labs",
        "action_label": "Open Lab Assistant",
    },
    "assistant": {
        "navigation": "AI Assistant",
        "title": "AI Assistant",
        "subtitle": "Provide faculty-aware help using approved course notes and lab manuals.",
        "metrics": (("KNOWLEDGE SOURCES", "18", "Course notes and manuals"), ("QUESTIONS TODAY", "27", "Student and faculty queries"), ("VOICE COMMANDS", "09", "Recognised in this demo"), ("RESPONSE STATUS", "READY", "Offline mode planned")),
        "assistant": ("Ask EduPilot about your course", "Example: Explain polymorphism or open the Java Lab Manual."),
        "activity": (("Knowledge-base entry added for DBMS Unit 3", "Today, 09:15 AM"), ("Lab manual shortcut updated for Java Lab", "Yesterday, 03:40 PM")),
        "status": "Assistant demo mode is ready",
        "action": "voice",
        "action_label": "Start Listening",
    },
    "reports": {
        "navigation": "Reports",
        "title": "Reports Centre",
        "subtitle": "Prepare concise attendance, academic, and lab progress reports.",
        "metrics": (("REPORTS READY", "04", "Attendance, marks, labs, tasks"), ("THIS WEEK", "12", "Reports generated"), ("EXPORT FORMATS", "02", "PDF and Excel planned"), ("PENDING EXPORTS", "03", "Awaiting approval")),
        "assistant": ("Reporting tools are prepared", "Generate an attendance summary or a lab-completion report."),
        "activity": (("Weekly attendance summary prepared", "Today, 08:20 AM"), ("Lab completion report saved as draft", "Yesterday, 02:10 PM")),
        "status": "Report templates available",
        "action": "info",
        "action_label": "Prepare Report",
    },
    "settings": {
        "navigation": "Settings",
        "title": "EduPilot Settings",
        "subtitle": "Manage preferences, privacy, accessibility, and assistant behaviour.",
        "metrics": (("VOICE LANGUAGE", "EN", "Tamil support planned"), ("PRIVACY MODE", "LOCAL", "On-device data by default"), ("NOTIFICATIONS", "ON", "Faculty alerts enabled"), ("SYSTEM VERSION", "0.1", "First-review prototype")),
        "assistant": ("EduPilot is configured for local-first use", "Privacy, permission, and accessibility controls will be available here."),
        "activity": (("Offline-first privacy mode selected", "Today, 09:00 AM"), ("Faculty profile verified for the demo", "Yesterday, 04:00 PM")),
        "status": "Local-first settings active",
        "action": "info",
        "action_label": "View Settings",
    },
}


STUDENT_MODULES = {
    "dashboard": {
        "navigation": "My Dashboard", "title": "Welcome to EduPilot!", "subtitle": "Your personal classroom and laboratory assistant.",
        "metrics": (("TODAY'S CLASSES", "04", "Next: Data Structures"), ("MY ATTENDANCE", "91%", "Above the required level"), ("PENDING TASKS", "03", "Due this week"), ("LAB PROGRESS", "75%", "9 of 12 experiments")),
        "assistant": ("Your study assistant is ready", "Ask about class work, attendance, or today's lab experiment."),
        "activity": (("Data Structures assignment submitted", "Today, 09:20 AM"), ("Java Lab experiment marked in progress", "Yesterday, 03:30 PM")),
        "status": "Ready to support your study day", "action": "voice", "action_label": "Start Listening",
    },
    "academics": {
        "navigation": "My Academics", "title": "My Academic Tracker", "subtitle": "See your marks, assignments, and subject-wise progress.",
        "metrics": (("CURRENT AVERAGE", "78%", "Improving this semester"), ("ASSIGNMENTS", "07/08", "One task pending"), ("INTERNAL MARKS", "82%", "Latest assessment"), ("LAB RECORD", "09/12", "Experiments completed")),
        "assistant": ("Your academic progress is clear", "Review pending assignments and subjects that need extra attention."),
        "activity": (("Internal marks published for Data Structures", "Today, 09:05 AM"), ("Reminder: DBMS assignment due Friday", "Today, 08:40 AM")),
        "status": "Academic record available", "action": "info", "action_label": "View My Progress",
    },
    "attendance": {
        "navigation": "My Attendance", "title": "My Attendance", "subtitle": "Track your attendance percentage and current class status.",
        "metrics": (("OVERALL ATTENDANCE", "91%", "Above 75% requirement"), ("PRESENT DAYS", "54", "This semester"), ("ABSENT DAYS", "05", "One medical leave"), ("CURRENT STATUS", "PRESENT", "III CSE - A, Period 1")),
        "assistant": ("Your attendance record is ready", "Check subject-wise attendance and eligibility status."),
        "activity": (("Marked present for Data Structures", "Today, 09:45 AM"), ("Attendance percentage updated", "Yesterday, 04:18 PM")),
        "status": "Attendance record is current", "action": "info", "action_label": "View Attendance Details",
    },
    "lab_progress": {
        "navigation": "My Lab Progress", "title": "My Lab Progress", "subtitle": "Follow your experiments, records, and lab completion status.",
        "metrics": (("EXPERIMENTS DONE", "09/12", "Three experiments remaining"), ("RECORD STATUS", "UPDATED", "Last updated today"), ("NEXT EXPERIMENT", "QUEUE", "Implement Queue using Array"), ("LAB MARKS", "84%", "Current average")),
        "assistant": ("Your lab progress is ready", "Open today's experiment or review your pending lab record work."),
        "activity": (("Experiment 9 marked completed", "Today, 09:00 AM"), ("Lab record feedback received", "Yesterday, 02:25 PM")),
        "status": "Lab progress available", "action": "labs", "action_label": "Open Lab Assistant",
    },
    "labs": {
        "navigation": "Lab Assistant", "title": "Lab Assistant", "subtitle": "Open tools, review the experiment, and keep your lab work on track.",
        "metrics": (("TODAY'S EXPERIMENT", "QUEUE", "Implement Queue using Array"), ("LAB SYSTEM", "READY", "System 18 assigned"), ("VS CODE", "AVAILABLE", "Open your workspace"), ("MANUAL", "READY", "Java Lab Manual")),
        "assistant": ("Your personal lab assistant is ready", "Open VS Code, check today's experiment, or review the lab manual."),
        "activity": (("System 18 reserved for your lab session", "Today, 08:50 AM"), ("Java Lab Manual opened last session", "Yesterday, 03:40 PM")),
        "status": "Lab workspace ready", "action": "labs", "action_label": "Open Lab Assistant",
    },
    "assistant": {
        "navigation": "AI Study Assistant", "title": "AI Study Assistant", "subtitle": "Ask course and lab questions using approved learning materials.",
        "metrics": (("COURSE NOTES", "18", "Approved references"), ("QUESTIONS TODAY", "06", "Your study queries"), ("VOICE MODE", "READY", "Offline plan"), ("HELP TOPIC", "DBMS", "Last selected subject")),
        "assistant": ("Ask EduPilot about your course", "Example: Explain polymorphism or show today's Java experiment."),
        "activity": (("Study topic opened: DBMS Normalisation", "Today, 08:55 AM"), ("Lab manual reference saved", "Yesterday, 06:05 PM")),
        "status": "Study assistant demo ready", "action": "voice", "action_label": "Start Listening",
    },
    "reports": {
        "navigation": "My Reports", "title": "My Reports", "subtitle": "Review your attendance, marks, assignments, and laboratory records.",
        "metrics": (("ATTENDANCE", "91%", "Current semester"), ("ACADEMIC AVG.", "78%", "Latest records"), ("ASSIGNMENTS", "07/08", "Submission history"), ("LAB RECORD", "09/12", "Completion history")),
        "assistant": ("Your academic report is ready", "Review your current progress before meeting your faculty advisor."),
        "activity": (("Attendance summary prepared", "Today, 08:20 AM"), ("Academic progress report updated", "Yesterday, 02:10 PM")),
        "status": "Personal reports available", "action": "info", "action_label": "View My Report",
    },
    "settings": {
        "navigation": "Profile & Settings", "title": "My Profile & Settings", "subtitle": "Manage your profile, accessibility, privacy, and preferences.",
        "metrics": (("PROFILE", "ACTIVE", "Student account"), ("NOTIFICATIONS", "ON", "Class and task alerts"), ("PRIVACY", "LOCAL", "Local-first project plan"), ("VERSION", "0.1", "First-review prototype")),
        "assistant": ("Your EduPilot profile is ready", "Accessibility and notification preferences will be managed here."),
        "activity": (("Student profile verified for the demo", "Today, 09:00 AM"), ("Notification preference enabled", "Yesterday, 04:00 PM")),
        "status": "Student profile active", "action": "info", "action_label": "View Profile Settings",
    },
}


class Dashboard(QMainWindow):
    """Role-specific EduPilot first-review UI prototype."""

    def __init__(self, role: str, user_name: str) -> None:
        super().__init__()
        self.role = role
        self.user_name = user_name
        self.modules = FACULTY_MODULES if role == "faculty" else STUDENT_MODULES
        self.current_module = "dashboard"

        ui_path = Path(__file__).resolve().parent.parent / "Dashboard.ui"
        ui_file = QFile(str(ui_path))
        if not ui_file.open(QFile.ReadOnly):
            raise RuntimeError(f"Could not open dashboard UI: {ui_path}")
        loaded_window = QUiLoader().load(ui_file)
        ui_file.close()
        if loaded_window is None:
            raise RuntimeError("Could not load Dashboard.ui")

        self.setStyleSheet(loaded_window.styleSheet())
        self.setCentralWidget(loaded_window.centralWidget())
        self.setStatusBar(loaded_window.statusBar())
        self.setWindowTitle("EduPilot - Classroom and Lab Assistant")
        self.setMinimumSize(loaded_window.minimumSize())
        self.resize(loaded_window.size())

        self.findChild(QLabel, "brandName").setText("EduPilot")
        self.findChild(QLabel, "brandCaption").setText("CLASSROOM & LAB ASSISTANT")
        self.findChild(QLabel, "profileName").setText(user_name)
        self.findChild(QLabel, "profileRole").setText("Faculty" if role == "faculty" else "Student")

        self.page_title = self.findChild(QLabel, "pageTitle")
        self.page_subtitle = self.findChild(QLabel, "pageSubtitle")
        self.card_labels = self.findChildren(QLabel, "cardLabel")
        self.card_values = self.findChildren(QLabel, "cardValue")
        self.card_meta = self.findChildren(QLabel, "cardMeta")
        self.voice_title = self.findChild(QLabel, "voiceTitle")
        self.voice_description = self.findChild(QLabel, "voiceDescription")
        self.activity_titles = self.findChildren(QLabel, "activityTitle")
        self.activity_times = self.findChildren(QLabel, "activityTime")
        self.status_ready = self.findChild(QLabel, "statusReady")
        self.status_caption = self.findChild(QLabel, "statusCaption")
        self.primary_button = self.findChild(QPushButton, "listenButton")
        self.primary_button.clicked.connect(self.handle_primary_action)

        self.nav_buttons = self.findChildren(QPushButton, "navButton")
        for button, module_name in zip(self.nav_buttons, self.modules):
            button.setText(self.modules[module_name]["navigation"])
            button.clicked.connect(lambda _checked=False, name=module_name: self.show_module(name))

        self.findChild(QFrame, "voicePanel").setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #0F386F, stop:0.55 #1556A6, stop:1 #194A88); "
            "border: 1px solid #2769B8; border-radius: 15px;"
        )
        self.findChild(QFrame, "quickPanel").setStyleSheet("background: #2A2E36; border: 1px solid #6F7785; border-radius: 14px;")
        self.findChild(QFrame, "micCircle").setStyleSheet("background: #162B62; border: 3px solid #5E9EFF; border-radius: 36px;")
        for activity in self.activity_titles:
            activity.setStyleSheet("color: #EDF1F7; font-size: 13px; font-weight: 600; padding-top: 8px;")

        self.show_module("dashboard")

    def show_module(self, module_name: str) -> None:
        self.current_module = module_name
        module = self.modules[module_name]
        self.page_title.setText(module["title"])
        self.page_subtitle.setText(module["subtitle"])
        for label, value, meta, content in zip(self.card_labels, self.card_values, self.card_meta, module["metrics"]):
            label.setText(content[0])
            value.setText(content[1])
            meta.setText(content[2])
        self.voice_title.setText(module["assistant"][0])
        self.voice_description.setText(module["assistant"][1])
        for title, timestamp, activity in zip(self.activity_titles, self.activity_times, module["activity"]):
            title.setText(f"*  {activity[0]}")
            timestamp.setText(f"     {activity[1]}")
        self.status_ready.setText("*  " + module["status"])
        self.status_caption.setText("UI prototype - data and voice integration are next-phase work")
        self.primary_button.setText(module["action_label"])
        self.statusBar().showMessage(f"EduPilot: {module['navigation']} view active")

    def handle_primary_action(self) -> None:
        action = self.modules[self.current_module]["action"]
        if action == "attendance":
            AttendanceTakerDialog(self).exec()
        elif action == "students":
            StudentDirectoryDialog(self).exec()
        elif action == "labs":
            LabAssistantDialog(self.role, self).exec()
        elif action == "voice":
            self.toggle_listening()
        else:
            QMessageBox.information(self, "EduPilot", "This workflow is included in the UI prototype. Database-backed records and report export are planned for the next development phase.")

    def toggle_listening(self) -> None:
        listening = self.primary_button.text().endswith("Stop Listening")
        self.primary_button.setText("Start Listening" if listening else "Stop Listening")
        self.statusBar().showMessage("Status: Ready" if listening else "Status: Listening... (UI prototype)", 3000)
