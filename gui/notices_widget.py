from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QTextEdit, QLineEdit,
    QComboBox, QMessageBox
)
from PySide6.QtCore import Qt
from database.database import (
    get_announcements,
    add_announcement,
    get_reminders,
    add_reminder,
    toggle_reminder_completed
)

class NoticesAndRemindersWidget(QWidget):
    """
    Announcements, Department Bulletins, and Voice Reminders Widget.
    """
    def __init__(self, user, role: str = "faculty"):
        super().__init__()
        self.user = user
        self.role = role
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Left Column: Announcements & Bulletins
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)

        ann_title = QLabel("Department Notices & Announcements")
        ann_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #60A5FA;")
        left_layout.addWidget(ann_title)

        self.list_announcements = QListWidget()
        self.list_announcements.setStyleSheet("""
            QListWidget { background-color: #1F2937; color: #E5E7EB; font-size: 13px; border-radius: 8px; padding: 10px; }
            QListWidget::item { border-bottom: 1px solid #374151; padding: 8px; }
        """)
        left_layout.addWidget(self.list_announcements)

        if self.role == "faculty":
            post_frame = QFrame()
            post_frame.setStyleSheet("background-color: #1E293B; border-radius: 8px; padding: 10px;")
            pf = QVBoxLayout(post_frame)

            post_lbl = QLabel("Post New Announcement")
            post_lbl.setStyleSheet("font-weight: bold; color: #34D399;")
            pf.addWidget(post_lbl)

            self.input_ann_title = QLineEdit()
            self.input_ann_title.setPlaceholderText("Notice Header / Title...")
            self.input_ann_title.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            self.input_ann_content = QTextEdit()
            self.input_ann_content.setPlaceholderText("Announcement Body...")
            self.input_ann_content.setMaximumHeight(70)
            self.input_ann_content.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            btn_post = QPushButton("Publish Announcement")
            btn_post.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
            btn_post.clicked.connect(self._post_announcement)

            pf.addWidget(self.input_ann_title)
            pf.addWidget(self.input_ann_content)
            pf.addWidget(btn_post)
            left_layout.addWidget(post_frame)

        main_layout.addWidget(left_widget)

        # Right Column: Smart Reminders
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        rem_title = QLabel("Smart Academic Reminders")
        rem_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #F59E0B;")
        right_layout.addWidget(rem_title)

        self.list_reminders = QListWidget()
        self.list_reminders.setStyleSheet("""
            QListWidget { background-color: #1F2937; color: #E5E7EB; font-size: 13px; border-radius: 8px; padding: 10px; }
            QListWidget::item { border-bottom: 1px solid #374151; padding: 8px; }
        """)
        self.list_reminders.itemDoubleClicked.connect(self._toggle_reminder)
        right_layout.addWidget(self.list_reminders)

        rem_frame = QFrame()
        rem_frame.setStyleSheet("background-color: #1E293B; border-radius: 8px; padding: 10px;")
        rf = QVBoxLayout(rem_frame)

        rf_lbl = QLabel("Add New Reminder")
        rf_lbl.setStyleSheet("font-weight: bold; color: #F59E0B;")
        rf.addWidget(rf_lbl)

        rh = QHBoxLayout()
        self.input_rem_title = QLineEdit()
        self.input_rem_title.setPlaceholderText("Reminder Task (e.g. Viva submission)...")
        self.input_rem_title.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

        self.combo_rem_type = QComboBox()
        self.combo_rem_type.addItems(["Assignment", "Lab Exam", "Viva", "General"])
        self.combo_rem_type.setStyleSheet("background-color: #374151; color: white; padding: 6px;")

        rh.addWidget(self.input_rem_title)
        rh.addWidget(self.combo_rem_type)
        rf.addLayout(rh)

        self.input_rem_date = QLineEdit()
        self.input_rem_date.setPlaceholderText("Due Date (YYYY-MM-DD)...")
        self.input_rem_date.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

        btn_add_rem = QPushButton("Add Reminder")
        btn_add_rem.setStyleSheet("background-color: #D97706; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        btn_add_rem.clicked.connect(self._add_reminder)

        rf.addWidget(self.input_rem_date)
        rf.addWidget(btn_add_rem)
        right_layout.addWidget(rem_frame)

        main_layout.addWidget(right_widget)

        self.load_announcements()
        self.load_reminders()

    def load_announcements(self):
        self.list_announcements.clear()
        anns = get_announcements()
        for a in anns:
            # a: (id, name, title, content, target_group, created_at)
            item_text = f"📢 [{a[5][:10]}] {a[2]}\nBy: {a[1]} | Target: {a[4]}\nDetails: {a[3]}"
            self.list_announcements.addItem(item_text)

    def load_reminders(self):
        self.list_reminders.clear()
        rems = get_reminders(self.user[0])
        for r in rems:
            # r: (id, title, reminder_type, due_date, is_completed)
            status_icon = "✅ [Completed]" if r[4] else "⏰ [Pending]"
            item_text = f"{status_icon} [{r[2]}] {r[1]} — Due: {r[3]}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, r[0])
            self.list_reminders.addItem(item)

    def _post_announcement(self):
        title = self.input_ann_title.text().strip()
        content = self.input_ann_content.toPlainText().strip()
        if not title or not content:
            QMessageBox.warning(self, "Warning", "Please provide title and content.")
            return

        add_announcement(self.user[0], title, content, target_group="All")
        QMessageBox.information(self, "Success", "Announcement posted!")
        self.input_ann_title.clear()
        self.input_ann_content.clear()
        self.load_announcements()

    def _add_reminder(self):
        title = self.input_rem_title.text().strip()
        rtype = self.combo_rem_type.currentText()
        due = self.input_rem_date.text().strip()
        if not title or not due:
            QMessageBox.warning(self, "Warning", "Please provide reminder task and due date.")
            return

        add_reminder(self.user[0], title, rtype, due)
        QMessageBox.information(self, "Success", "Reminder saved!")
        self.input_rem_title.clear()
        self.input_rem_date.clear()
        self.load_reminders()

    def _toggle_reminder(self, item):
        rem_id = item.data(Qt.UserRole)
        if rem_id:
            toggle_reminder_completed(rem_id)
            self.load_reminders()
