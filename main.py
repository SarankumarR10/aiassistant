import sys

from PySide6.QtWidgets import QApplication

from database.database import initialize_database

from gui.login import LoginWindow


def main():

    # Initialize EduPilot database
    initialize_database()

    # Create Qt application
    app = QApplication(sys.argv)

    app.setApplicationName("EduPilot")

    # Open login screen
    window = LoginWindow()
    window.show()

    # Start application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()