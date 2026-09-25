from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QSplitter, QGroupBox, QFileDialog,
    QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt
from pathlib import Path
import re
from lab.code_runner import code_runner
from gui.theme import POSITIVUS_QSS, create_section_header

SAMPLE_CODE = {
    "Python": "def main():\n    print('EduPilot Code Runner')\n    for i in range(1, 6):\n        print(f'Step {i}: Code Execution Successful')\n\nif __name__ == '__main__':\n    main()",
    "Java": "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello from EduPilot Java Environment!\");\n    }\n}",
    "C": "#include <stdio.h>\nint main() {\n    printf(\"Hello from EduPilot C Code Runner!\\n\");\n    return 0;\n}",
    "C++": "#include <iostream>\nusing namespace std;\nint main() {\n    cout << \"Hello from EduPilot C++ Code Runner!\" << endl;\n    return 0;\n}"
}

class CodeRunnerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header controls
        top_bar = QHBoxLayout()
        header = create_section_header("Isolated Code Runner & AI Tutor", "Runs code in a restricted Docker container with no network")
        top_bar.addWidget(header)
        top_bar.addStretch()

        lbl_lang = QLabel("Language:")
        lbl_lang.setStyleSheet("font-weight: 600; font-size: 13px; color: #0F172A;")

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "Java", "C", "C++"])
        self.lang_combo.currentTextChanged.connect(self._on_lang_changed)

        self.run_btn = QPushButton("Run Code")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setProperty("class", "secondary")
        self.run_btn.clicked.connect(self.run_code)

        self.new_project_btn = QPushButton("New Project")
        self.new_project_btn.setProperty("class", "outline")
        self.new_project_btn.clicked.connect(self.create_project)

        top_bar.addWidget(lbl_lang)
        top_bar.addWidget(self.lang_combo)
        top_bar.addWidget(self.new_project_btn)
        top_bar.addWidget(self.run_btn)

        layout.addLayout(top_bar)
        layout.addSpacing(10)

        # Main splitter (Code Editor vs Console & AI Explanation)
        splitter = QSplitter(Qt.Vertical)

        # Code Editor Group
        editor_group = QGroupBox("Source Code Editor")
        editor_group.setStyleSheet("""
            QGroupBox {
                font-weight: 700;
                font-size: 13px;
                color: #0F172A;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                margin-top: 10px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        ed_layout = QVBoxLayout(editor_group)
        self.code_edit = QTextEdit()
        self.code_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                border: 1px solid #0F172A;
                border-radius: 6px;
            }
        """)
        self.code_edit.setPlainText(SAMPLE_CODE["Python"])
        ed_layout.addWidget(self.code_edit)

        # Output Console & AI Explanation Splitter
        bottom_splitter = QSplitter(Qt.Horizontal)

        out_group = QGroupBox("Execution Console Output")
        out_group.setStyleSheet("""
            QGroupBox {
                font-weight: 700;
                font-size: 13px;
                color: #0F172A;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                margin-top: 10px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        out_layout = QVBoxLayout(out_group)
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                border: 1px solid #0F172A;
                border-radius: 6px;
            }
        """)
        out_layout.addWidget(self.output_edit)

        ai_group = QGroupBox("AI Error Tutor & Suggestions")
        ai_group.setStyleSheet("""
            QGroupBox {
                font-weight: 700;
                font-size: 13px;
                color: #0F172A;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                margin-top: 10px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        ai_layout = QVBoxLayout(ai_group)
        self.ai_edit = QTextEdit()
        self.ai_edit.setReadOnly(True)
        self.ai_edit.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFC;
                color: #0F172A;
                font-size: 13px;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
            }
        """)
        ai_layout.addWidget(self.ai_edit)

        bottom_splitter.addWidget(out_group)
        bottom_splitter.addWidget(ai_group)

        splitter.addWidget(editor_group)
        splitter.addWidget(bottom_splitter)

        layout.addWidget(splitter)

    def _on_lang_changed(self, lang_name):
        self.code_edit.setPlainText(SAMPLE_CODE.get(lang_name, ""))

    def create_project(self):
        name, accepted = QInputDialog.getText(self, "Create Local Project", "Project folder name:")
        if not accepted:
            return
        name = name.strip()
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,63}", name)
                or name in {".", ".."}
                or name.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            QMessageBox.warning(self, "Project name", "Use 1–64 letters, numbers, spaces, hyphens, or underscores. Choose a name that is not reserved by Windows.")
            return

        language, accepted = QInputDialog.getItem(
            self, "Project Language", "Choose a starter language:", list(SAMPLE_CODE), 0, False
        )
        if not accepted:
            return
        parent = QFileDialog.getExistingDirectory(self, "Choose Parent Folder for Project")
        if not parent:
            return
        project_path = Path(parent) / name
        if project_path.exists():
            QMessageBox.warning(self, "Project already exists", "That folder already exists. Choose a different name or parent folder; existing files will not be overwritten.")
            return
        answer = QMessageBox.question(
            self, "Confirm Project Creation",
            f"Create a {language} starter project at:\n{project_path}",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return

        source_names = {"Python": "main.py", "Java": "Main.java", "C": "main.c", "C++": "main.cpp"}
        try:
            project_path.mkdir(parents=False, exist_ok=False)
            with (project_path / source_names[language]).open("x", encoding="utf-8") as source_file:
                source_file.write(SAMPLE_CODE[language] + "\n")
            with (project_path / "README.md").open("x", encoding="utf-8") as readme:
                readme.write(f"# {name}\n\nEduPilot {language} starter project.\n")
        except FileExistsError:
            QMessageBox.warning(self, "Project already exists", "That folder was created by another process. Existing files were not overwritten.")
            return
        except OSError as error:
            QMessageBox.warning(self, "Could not create project", f"The project folder could not be created: {error}")
            return

        self.lang_combo.setCurrentText(language)
        self.code_edit.setPlainText(SAMPLE_CODE[language])
        self.output_edit.setPlainText(f"Created {language} starter project at {project_path}")
        QMessageBox.information(self, "Project created", f"Starter source and README were created in:\n{project_path}")

    def run_code(self):
        from PySide6.QtWidgets import QMessageBox
        lang = self.lang_combo.currentText()
        code = self.code_edit.toPlainText()
        if not code.strip():
            QMessageBox.warning(self, "Code required", "Write or load a program before running it.")
            return
        if len(code) > 100_000:
            QMessageBox.warning(self, "Code too large", "Programs are limited to 100,000 characters.")
            return
        choice = QMessageBox.warning(
            self, "Run code in the sandbox?",
            "This runs in an isolated container with no network, a read-only system, and limited memory, processes, and time. Continue?",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
        )
        if choice != QMessageBox.Yes:
            return
        self.output_edit.setPlainText("Executing code, please wait...")
        self.ai_edit.clear()

        res = code_runner.execute(lang, code)
        self.output_edit.setPlainText(res["output"])
        if res["status"] == "success":
            self.ai_edit.setPlainText("Program completed in the isolated runner.")
        elif res["ai_explanation"]:
            self.ai_edit.setPlainText(res["ai_explanation"])
        else:
            self.ai_edit.clear()
