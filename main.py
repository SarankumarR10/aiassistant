import sys
from PySide6.QtWidgets import QApplication, QMessageBox

from database.database import initialize_database
from gui.login import LoginWindow
from gui.theme import POSITIVUS_QSS, install_app_fonts


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EduPilot")
    install_app_fonts(app)
    app.setStyleSheet(POSITIVUS_QSS)

    try:
        initialize_database()
    except Exception as error:
        QMessageBox.critical(
            None,
            "EduPilot could not start",
            "EduPilot could not prepare its local database. Check that the application data folder is writable.\n\n"
            f"Details: {error}",
        )
        return 1

    # Open login screen
    window = LoginWindow()
    window.show()

    # Start application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
