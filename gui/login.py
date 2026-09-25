from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QMessageBox,
    QFrame
)
from PySide6.QtCore import Qt

from database.database import authenticate_user
from gui.faculty_dashboard import FacultyDashboard
from gui.student_dashboard import StudentDashboard
from gui.theme import POSITIVUS_QSS


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.dashboard = None

        self.setWindowTitle("EduPilot - Intelligent Workspace Login")
        self.setMinimumSize(900, 580)
        self.resize(1040, 660)

        self.build_ui()

    def build_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)

        main = QHBoxLayout(self)
        main.setContentsMargins(64, 52, 64, 52)
        main.setSpacing(72)

        # Minimal product introduction: keep the focus on sign-in.
        intro = QVBoxLayout()
        intro.setSpacing(0)
        wordmark = QLabel("EduPilot")
        wordmark.setStyleSheet("font-size: 18px; font-weight: 700; color: #354E60; letter-spacing: 0.3px;")
        title_lbl = QLabel("Your classroom,\nin one workspace.")
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("font-size: 34px; font-weight: 700; color: #26323B; margin-top: 34px;")
        description = QLabel("A shared workspace for teaching, learning, attendance, and lab work.")
        description.setWordWrap(True)
        description.setStyleSheet("color: #687782; font-size: 15px; margin-top: 14px; line-height: 1.45;")
        intro.addWidget(wordmark)
        intro.addWidget(title_lbl)
        intro.addWidget(description)
        intro.addStretch()

        # Single sign-in surface; no secondary capability panels.
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(380)
        card.setStyleSheet("""
            QFrame#loginCard {
                background-color: #FFFFFF;
                border: 1px solid #DCE2E7;
                border-radius: 12px;
            }
            QLabel {
                color: #26323B;
                font-size: 13px;
                font-weight: 600;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 32, 30, 30)
        card_layout.setSpacing(7)

        card_title = QLabel("Sign In")
        card_title.setStyleSheet("""
            font-size: 22px;
            font-weight: 700;
            color: #26323B;
            letter-spacing: -0.3px;
        """)

        subtitle = QLabel("Enter your workspace credentials to continue")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #687782; font-size: 12px; font-weight: 400;")

        role_label = QLabel("Role Portal")
        self.role = QComboBox()
        self.role.addItems(["Faculty", "Student"])

        username_label = QLabel("Username / ID")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter username")

        password_label = QLabel("Password")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setEchoMode(QLineEdit.Password)

        self.login_button = QPushButton("Sign In to Workspace")
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #48677D;
                color: #FFFFFF;
                border: 1px solid #48677D;
                border-radius: 8px;
                padding: 11px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #354E60;
                border: 1px solid #354E60;
            }
        """)
        self.login_button.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)

        card_layout.addWidget(card_title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(16)

        card_layout.addWidget(role_label)
        card_layout.addWidget(self.role)
        card_layout.addSpacing(7)

        card_layout.addWidget(username_label)
        card_layout.addWidget(self.username)
        card_layout.addSpacing(7)

        card_layout.addWidget(password_label)
        card_layout.addWidget(self.password)
        card_layout.addSpacing(16)

        card_layout.addWidget(self.login_button)
        card_layout.addStretch()

        main.addLayout(intro, 1)
        main.addWidget(card, 0, Qt.AlignVCenter)

    def login(self):
        username = self.username.text().strip()
        password = self.password.text()

        if not username or not password:
            QMessageBox.warning(
                self,
                "Login",
                "Please enter username and password."
            )
            return

        user = authenticate_user(username, password)

        if user is None:
            QMessageBox.warning(
                self,
                "Login Failed",
                "Invalid username or password."
            )
            return

        selected_role = self.role.currentText().lower()

        if user[2] != selected_role:
            QMessageBox.warning(
                self,
                "Role Mismatch",
                f"This account belongs to {user[2].title()}."
            )
            return

        self.hide()

        if user[2] == "faculty":
            self.dashboard = FacultyDashboard(
                user,
                self.show_login
            )
        else:
            self.dashboard = StudentDashboard(
                user,
                self.show_login
            )

        self.dashboard.show()

    def show_login(self):
        self.username.clear()
        self.password.clear()

        self.show()
        self.raise_()
        self.activateWindow()
