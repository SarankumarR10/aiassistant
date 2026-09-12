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


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.dashboard = None

        self.setWindowTitle("EduPilot - Login")
        self.resize(900, 600)

        self.build_ui()

    def build_ui(self):

        self.setStyleSheet("""
            QWidget {
                background-color: #0F172A;
                color: white;
            }

            QLineEdit, QComboBox {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 12px;
                color: white;
                font-size: 14px;
            }

            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #3B82F6;
            }

            QPushButton {
                background-color: #2563EB;
                border: none;
                border-radius: 8px;
                padding: 13px;
                color: white;
                font-size: 15px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #3B82F6;
            }
        """)

        main = QHBoxLayout(self)
        main.setContentsMargins(60, 45, 60, 45)
        main.setSpacing(60)

        # LEFT

        left = QVBoxLayout()

        brand = QLabel("EDUPILOT")
        brand.setStyleSheet("""
            font-size: 38px;
            font-weight: bold;
            color: #60A5FA;
        """)

        tagline = QLabel(
            "Your Intelligent Classroom & Lab Assistant"
        )

        tagline.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
        """)

        description = QLabel(
            "Offline-first personal assistant for students "
            "and faculty members."
        )

        description.setWordWrap(True)
        description.setStyleSheet("""
            color: #94A3B8;
            font-size: 14px;
        """)

        features = QLabel(
            "\nSmart Attendance\n"
            "Academic Tracking\n"
            "AI Study Assistant\n"
            "Smart Lab Assistant\n"
            "Offline Voice Commands"
        )

        features.setStyleSheet("""
            color: #CBD5E1;
            font-size: 15px;
            line-height: 1.5;
        """)

        left.addWidget(brand)
        left.addSpacing(20)
        left.addWidget(tagline)
        left.addSpacing(15)
        left.addWidget(description)
        left.addSpacing(25)
        left.addWidget(features)
        left.addStretch()

        # RIGHT LOGIN CARD

        card = QFrame()

        card.setFixedWidth(350)

        card.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 20px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 35, 30, 35)

        title = QLabel("Welcome Back")
        title.setStyleSheet("""
            font-size: 25px;
            font-weight: bold;
        """)

        subtitle = QLabel(
            "Sign in to continue to EduPilot"
        )

        subtitle.setStyleSheet(
            "color: #94A3B8;"
        )

        role_label = QLabel("Login as")

        self.role = QComboBox()
        self.role.addItems([
            "Faculty",
            "Student"
        ])

        username_label = QLabel("Username")

        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter username")

        password_label = QLabel("Password")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Enter password")
        self.password.setEchoMode(QLineEdit.Password)

        self.login_button = QPushButton("Sign In")
        self.login_button.clicked.connect(self.login)

        self.password.returnPressed.connect(self.login)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(25)

        card_layout.addWidget(role_label)
        card_layout.addWidget(self.role)

        card_layout.addSpacing(12)

        card_layout.addWidget(username_label)
        card_layout.addWidget(self.username)

        card_layout.addSpacing(12)

        card_layout.addWidget(password_label)
        card_layout.addWidget(self.password)

        card_layout.addSpacing(25)

        card_layout.addWidget(self.login_button)

        card_layout.addStretch()

        main.addLayout(left, 1)
        main.addWidget(card)

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