from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QTextEdit, QLineEdit,
    QComboBox, QMessageBox
)
from PySide6.QtCore import Qt
from datetime import date
from database.database import (
    get_announcements,
    add_announcement,
    get_reminders,
    add_reminder,
    toggle_reminder_completed
)
from gui.theme import POSITIVUS_QSS, create_section_header, configure_wrapped_list

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
        self.setStyleSheet(POSITIVUS_QSS)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(16)

        header = create_section_header("Notices & Academic Reminders")
        outer_layout.addWidget(header)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(16)

        # Left Column: Announcements & Bulletins
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)

        ann_title = QLabel("Department Notices & Announcements")
        ann_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        left_layout.addWidget(ann_title)

        self.list_announcements = QListWidget()
        configure_wrapped_list(self.list_announcements)
        left_layout.addWidget(self.list_announcements)

        if self.role == "faculty":
            post_frame = QFrame()
            post_frame.setObjectName("surfaceCard")
            post_frame.setStyleSheet("""
                QFrame#surfaceCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                    padding: 14px;
                }
            """)
            pf = QVBoxLayout(post_frame)

            post_lbl = QLabel("Post New Announcement")
            post_lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #0F172A;")
            pf.addWidget(post_lbl)

            self.input_ann_title = QLineEdit()
            self.input_ann_title.setPlaceholderText("Notice Header / Title...")

            self.combo_audience = QComboBox()
            self.combo_audience.addItems(["All", "Students", "Faculty"])

            self.input_ann_content = QTextEdit()
            self.input_ann_content.setPlaceholderText("Announcement Body...")
            self.input_ann_content.setMaximumHeight(70)

            btn_post = QPushButton("Publish Announcement")
            btn_post.setCursor(Qt.PointingHandCursor)
            btn_post.setProperty("class", "secondary")
            btn_post.clicked.connect(self._post_announcement)

            pf.addWidget(self.input_ann_title)
            pf.addWidget(self.combo_audience)
            pf.addWidget(self.input_ann_content)
            pf.addWidget(btn_post)
            left_layout.addWidget(post_frame)

        main_layout.addWidget(left_widget)

        # Right Column: Smart Reminders
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        rem_title = QLabel("Academic Reminders")
        rem_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        right_layout.addWidget(rem_title)

        self.list_reminders = QListWidget()
        configure_wrapped_list(self.list_reminders)
        self.list_reminders.itemDoubleClicked.connect(self._toggle_reminder)
        right_layout.addWidget(self.list_reminders)

        rem_frame = QFrame()
        rem_frame.setObjectName("surfaceCard")
        rem_frame.setStyleSheet("""
            QFrame#surfaceCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        rf = QVBoxLayout(rem_frame)

        rf_lbl = QLabel("Add New Reminder")
        rf_lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #0F172A;")
        rf.addWidget(rf_lbl)

        rh = QHBoxLayout()
        self.combo_priority = QComboBox()
        self.combo_priority.addItems(["Low", "Normal", "High", "Urgent"])

        self.input_due_date = QLineEdit()
        self.input_due_date.setPlaceholderText("Due Date (YYYY-MM-DD)...")

        rh.addWidget(self.combo_priority)
        rh.addWidget(self.input_due_date)
        rf.addLayout(rh)

        self.input_rem_text = QLineEdit()
        self.input_rem_text.setPlaceholderText("Reminder description...")

        btn_rem = QPushButton("Add Reminder")
        btn_rem.setCursor(Qt.PointingHandCursor)
        btn_rem.clicked.connect(self._add_reminder)

        rf.addWidget(self.input_rem_text)
        rf.addWidget(btn_rem)

        right_layout.addWidget(rem_frame)
        main_layout.addWidget(right_widget)

        outer_layout.addLayout(main_layout)

        self.load_announcements()
        self.load_reminders()

    def load_announcements(self):
        anns = get_announcements(self.role)
        self.list_announcements.clear()
        for a in anns:
            created = a[5] if len(a) > 5 else "Recent"
            item_text = f"Notice: {a[2]}  [Audience: {a[4]} | Author: {a[1]} - {created}]\n   {a[3]}"
            self.list_announcements.addItem(item_text)

    def _post_announcement(self):
        title = self.input_ann_title.text().strip()
        body = self.input_ann_content.toPlainText().strip()
        if not title or not body:
            QMessageBox.warning(self, "Warning", "Title and Body are required.")
            return

        add_announcement(
            faculty_id=self.user[0], title=title, content=body,
            target_group=self.combo_audience.currentText(),
        )
        QMessageBox.information(self, "Success", "Announcement posted successfully!")
        self.input_ann_title.clear()
        self.input_ann_content.clear()
        self.load_announcements()

    def load_reminders(self):
        rems = get_reminders(self.user[0])
        self.current_rems = rems
        self.list_reminders.clear()
        for r in rems:
            status = "Completed" if r[4] else "Pending"
            self.list_reminders.addItem(f"[{r[2]}] {r[1]} (Due: {r[3]}) - Status: {status} (Double click to toggle)")

    def _add_reminder(self):
        text = self.input_rem_text.text().strip()
        prio = self.combo_priority.currentText()
        due = self.input_due_date.text().strip()

        if not text:
            QMessageBox.warning(self, "Warning", "Reminder description is required.")
            return

        try:
            date.fromisoformat(due)
        except ValueError:
            QMessageBox.warning(self, "Invalid due date", "Enter the due date as YYYY-MM-DD.")
            return

        add_reminder(self.user[0], text, prio, due)
        QMessageBox.information(self, "Success", "Reminder added!")
        self.input_rem_text.clear()
        self.input_due_date.clear()
        self.load_reminders()

    def _toggle_reminder(self, item: QListWidgetItem):
        row = self.list_reminders.row(item)
        if hasattr(self, 'current_rems') and row < len(self.current_rems):
            rem_id = self.current_rems[row][0]
            toggle_reminder_completed(rem_id, self.user[0])
            self.load_reminders()
