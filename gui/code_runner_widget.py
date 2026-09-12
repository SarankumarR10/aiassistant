from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QSplitter, QGroupBox
)
from PySide6.QtCore import Qt
from lab.code_runner import code_runner

SAMPLE_CODE = {
    "Python": "def main():\n    print('VCET Assistant Code Runner')\n    for i in range(1, 6):\n        print(f'Step {i}: Code Execution Successful')\n\nif __name__ == '__main__':\n    main()",
    "Java": "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello from VCET Java Environment!\");\n    }\n}",
    "C": "#include <stdio.h>\nint main() {\n    printf(\"Hello from C Code Execution Engine!\\n\");\n    return 0;\n}",
    "C++": "#include <iostream>\nusing namespace std;\nint main() {\n    cout << \"Hello from C++ Code Runner!\" << endl;\n    return 0;\n}"
}

class CodeRunnerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header controls
        top_bar = QHBoxLayout()
        title = QLabel("Offline Code Runner & AI Error Tutor")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "Java", "C", "C++"])
        self.lang_combo.setStyleSheet("background-color: #2a2a3d; color: #ffffff; padding: 5px; font-size: 13px;")
        self.lang_combo.currentTextChanged.connect(self._on_lang_changed)

        self.run_btn = QPushButton("▶ Run Code")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.run_btn.clicked.connect(self.run_code)

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("Language:"))
        top_bar.addWidget(self.lang_combo)
        top_bar.addWidget(self.run_btn)

        layout.addLayout(top_bar)

        # Main splitter (Code Editor vs Console & AI Explanation)
        splitter = QSplitter(Qt.Vertical)

        # Code Editor Group
        editor_group = QGroupBox("Source Code")
        editor_group.setStyleSheet("color: #3498db; font-weight: bold;")
        ed_layout = QVBoxLayout(editor_group)
        self.code_edit = QTextEdit()
        self.code_edit.setStyleSheet("""
            QTextEdit {
                background-color: #12121c;
                color: #00ffcc;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid #2e2e42;
            }
        """)
        self.code_edit.setPlainText(SAMPLE_CODE["Python"])
        ed_layout.addWidget(self.code_edit)

        # Output Console & AI Explanation Splitter
        bottom_splitter = QSplitter(Qt.Horizontal)

        out_group = QGroupBox("Execution Output")
        out_group.setStyleSheet("color: #2ecc71; font-weight: bold;")
        out_layout = QVBoxLayout(out_group)
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d14;
                color: #ffffff;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        out_layout.addWidget(self.output_edit)

        ai_group = QGroupBox("AI Error Tutor & Suggestions")
        ai_group.setStyleSheet("color: #f39c12; font-weight: bold;")
        ai_layout = QVBoxLayout(ai_group)
        self.ai_edit = QTextEdit()
        self.ai_edit.setReadOnly(True)
        self.ai_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1a1710;
                color: #f1c40f;
                font-size: 13px;
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

    def run_code(self):
        lang = self.lang_combo.currentText()
        code = self.code_edit.toPlainText()
        self.output_edit.setPlainText("Executing code, please wait...")
        self.ai_edit.clear()

        res = code_runner.execute(lang, code)
        self.output_edit.setPlainText(res["output"])
        if res["ai_explanation"]:
            self.ai_edit.setPlainText(res["ai_explanation"])
        else:
            self.ai_edit.setPlainText("No errors detected! Program ran cleanly.")
