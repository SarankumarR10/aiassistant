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
    toggle_reminder_completed,
    get_academic_classes,
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

        announcement_filters = QHBoxLayout()
        self.announcement_search = QLineEdit()
        self.announcement_search.setPlaceholderText("Search notices by title or content")
        self.announcement_search.textChanged.connect(self._render_announcements)
        self.announcement_class_filter = QComboBox()
        self.announcement_class_filter.addItem("All my classes", None)
        classes = get_academic_classes(
            faculty_id=self.user[0] if self.role == "faculty" else None,
            student_user_id=self.user[0] if self.role == "student" else None,
        )
        for class_row in classes:
            class_label = f"{class_row[1]} · Year {class_row[2]} · Section {class_row[3]}"
            self.announcement_class_filter.addItem(class_label, class_row[0])
        self.announcement_class_filter.currentIndexChanged.connect(self._render_announcements)
        self.refresh_announcements_button = QPushButton("Refresh")
        self.refresh_announcements_button.setProperty("class", "outline")
        self.refresh_announcements_button.clicked.connect(self.load_announcements)
        announcement_filters.addWidget(self.announcement_search, 1)
        announcement_filters.addWidget(self.announcement_class_filter)
        announcement_filters.addWidget(self.refresh_announcements_button)
        left_layout.addLayout(announcement_filters)

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
            self.class_picker = QComboBox()
            self.class_picker.addItem("All classes", None)
            for class_row in get_academic_classes(faculty_id=self.user[0]):
                self.class_picker.addItem(
                    f"{class_row[1]} · Year {class_row[2]} · Section {class_row[3]} · {class_row[4]}",
                    class_row[0],
                )

            self.input_ann_content = QTextEdit()
            self.input_ann_content.setPlaceholderText("Announcement Body...")
            self.input_ann_content.setMaximumHeight(70)

            btn_post = QPushButton("Publish Announcement")
            btn_post.setCursor(Qt.PointingHandCursor)
            btn_post.setProperty("class", "secondary")
            btn_post.clicked.connect(self._post_announcement)

            pf.addWidget(self.input_ann_title)
            pf.addWidget(self.combo_audience)
            pf.addWidget(QLabel("Class (optional)"))
            pf.addWidget(self.class_picker)
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

        reminder_filters = QHBoxLayout()
        self.reminder_status_filter = QComboBox()
        self.reminder_status_filter.addItem("All reminders", None)
        self.reminder_status_filter.addItem("Pending", False)
        self.reminder_status_filter.addItem("Completed", True)
        self.reminder_status_filter.currentIndexChanged.connect(self._render_reminders)
        self.toggle_reminder_button = QPushButton("Mark selected complete")
        self.toggle_reminder_button.setProperty("class", "outline")
        self.toggle_reminder_button.setEnabled(False)
        self.toggle_reminder_button.clicked.connect(self._toggle_selected_reminder)
        reminder_filters.addWidget(self.reminder_status_filter, 1)
        reminder_filters.addWidget(self.toggle_reminder_button)
        right_layout.addLayout(reminder_filters)

        self.list_reminders = QListWidget()
        configure_wrapped_list(self.list_reminders)
        self.list_reminders.itemDoubleClicked.connect(self._toggle_reminder)
        self.list_reminders.itemSelectionChanged.connect(self._update_reminder_button)
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
        self.announcements = get_announcements(self.role, user_id=self.user[0])
        self._render_announcements()

    def _render_announcements(self, *_):
        anns = getattr(self, "announcements", [])
        search = self.announcement_search.text().strip().casefold()
        selected_class = self.announcement_class_filter.currentData()
        self.list_announcements.clear()
        for a in anns:
            if selected_class is not None and a[6] not in (None, selected_class):
                continue
            if search and search not in f"{a[2]} {a[3]} {a[1]}".casefold():
                continue
            created = a[5] if len(a) > 5 else "Recent"
            class_label = f"{a[7]} Year {a[8]} Section {a[9]} · {a[10]}" if len(a) > 10 and a[7] else "All classes"
            item_text = f"Notice: {a[2]}  [Audience: {a[4]} | {class_label} | Author: {a[1]} - {created}]\n   {a[3]}"
            self.list_announcements.addItem(item_text)
        if self.list_announcements.count() == 0:
            self.list_announcements.addItem("No notices match these filters.")

    def _post_announcement(self):
        title = self.input_ann_title.text().strip()
        body = self.input_ann_content.toPlainText().strip()
        if not title or not body:
            QMessageBox.warning(self, "Warning", "Title and Body are required.")
            return

        add_announcement(
            faculty_id=self.user[0], title=title, content=body,
            target_group=self.combo_audience.currentText(), class_id=self.class_picker.currentData(),
        )
        QMessageBox.information(self, "Success", "Announcement posted successfully!")
        self.input_ann_title.clear()
        self.input_ann_content.clear()
        self.load_announcements()

    def load_reminders(self):
        self.current_rems = get_reminders(self.user[0])
        self._render_reminders()

    def _render_reminders(self, *_):
        self.list_reminders.clear()
        completed_filter = self.reminder_status_filter.currentData()
        for r in self.current_rems:
            if completed_filter is not None and bool(r[4]) != completed_filter:
                continue
            status = "Completed" if r[4] else "Pending"
            item = QListWidgetItem(f"[{r[2]}] {r[1]} (Due: {r[3]}) · {status}")
            item.setData(Qt.UserRole, r[0])
            self.list_reminders.addItem(item)
        if self.list_reminders.count() == 0:
            self.list_reminders.addItem("No reminders match this filter.")
        self._update_reminder_button()

    def _update_reminder_button(self):
        item = self.list_reminders.currentItem()
        reminder_id = item.data(Qt.UserRole) if item else None
        reminder = next((row for row in getattr(self, "current_rems", [])
                         if row[0] == reminder_id), None)
        if reminder:
            label = "Mark selected pending" if reminder[4] else "Mark selected complete"
            self.toggle_reminder_button.setText(label)
        self.toggle_reminder_button.setEnabled(reminder is not None)

    def _toggle_selected_reminder(self):
        self._toggle_reminder(self.list_reminders.currentItem())

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
        if item is None:
            return
        rem_id = item.data(Qt.UserRole)
        if rem_id is not None:
            toggle_reminder_completed(rem_id, self.user[0])
            self.load_reminders()
