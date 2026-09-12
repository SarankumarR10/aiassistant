from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QTabWidget,
    QListWidget, QFrame
)
from PySide6.QtCore import Qt
from database.database import (
    get_subjects,
    get_notes,
    add_note,
    get_question_banks,
    add_question_bank_item
)
from ai.rag_engine import rag_engine

class NotesAndQuestionBankWidget(QWidget):
    """
    Unit Notes, Lab Manuals, and Model Question Bank Browser Widget.
    """
    def __init__(self, user, role: str = "faculty"):
        super().__init__()
        self.user = user
        self.role = role
        self.subjects = get_subjects()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Course Knowledge Base & Question Bank")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #374151; background: #111827; border-radius: 8px; }
            QTabBar::tab { background: #1F2937; color: #94A3B8; padding: 10px 20px; font-weight: bold; }
            QTabBar::tab:selected { background: #2563EB; color: white; border-radius: 4px; }
        """)

        tabs.addTab(self._build_notes_tab(), "Unit Notes & Manuals")
        tabs.addTab(self._build_qbank_tab(), "Unit Question Bank")

        layout.addWidget(tabs)

    def _build_notes_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(15, 15, 15, 15)

        lbl = QLabel("Uploaded Lecture Notes & Reference Manuals")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #60A5FA;")
        layout.addWidget(lbl)

        self.table_notes = QTableWidget()
        self.table_notes.setColumnCount(5)
        self.table_notes.setHorizontalHeaderLabels(["ID", "Subject", "Unit #", "Title", "File Path"])
        self.table_notes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_notes.setStyleSheet("""
            QTableWidget { background-color: #1F2937; color: white; gridline-color: #374151; font-size: 13px; }
            QHeaderView::section { background-color: #0F172A; color: #60A5FA; font-weight: bold; }
        """)
        layout.addWidget(self.table_notes)

        if self.role == "faculty":
            form_frame = QFrame()
            form_frame.setStyleSheet("background-color: #1E293B; border-radius: 8px; padding: 10px;")
            form_layout = QVBoxLayout(form_frame)

            form_title = QLabel("Upload New Lecture Note / Manual PDF")
            form_title.setStyleSheet("font-weight: bold; color: #34D399;")
            form_layout.addWidget(form_title)

            h1 = QHBoxLayout()
            self.combo_note_subject = QComboBox()
            for s in self.subjects:
                self.combo_note_subject.addItem(f"{s[1]} - {s[2]}", s[0])
            self.combo_note_subject.setStyleSheet("background-color: #374151; color: white; padding: 6px;")

            self.combo_unit = QComboBox()
            for u in range(1, 6):
                self.combo_unit.addItem(f"Unit {u}", u)
            self.combo_unit.setStyleSheet("background-color: #374151; color: white; padding: 6px;")

            h1.addWidget(self.combo_note_subject)
            h1.addWidget(self.combo_unit)
            form_layout.addLayout(h1)

            self.input_note_title = QLineEdit()
            self.input_note_title.setPlaceholderText("Document Title (e.g., Unit 2 Normalization Notes)...")
            self.input_note_title.setStyleSheet("background-color: #374151; color: white; padding: 8px;")
            form_layout.addWidget(self.input_note_title)

            h2 = QHBoxLayout()
            self.input_note_filepath = QLineEdit()
            self.input_note_filepath.setPlaceholderText("File Path (.pdf, .txt, .md)...")
            self.input_note_filepath.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            btn_browse = QPushButton("Browse")
            btn_browse.setStyleSheet("background-color: #374151; color: white; padding: 8px;")
            btn_browse.clicked.connect(self._browse_note_file)

            h2.addWidget(self.input_note_filepath)
            h2.addWidget(btn_browse)
            form_layout.addLayout(h2)

            btn_upload = QPushButton(" Upload & Index into AI RAG Engine")
            btn_upload.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
            btn_upload.clicked.connect(self._upload_and_index_note)
            form_layout.addWidget(btn_upload)

            layout.addWidget(form_frame)

        self.load_notes()
        return page

    def _build_qbank_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(15, 15, 15, 15)

        header_h = QHBoxLayout()
        lbl = QLabel("Unit-wise Model Question Bank & Answer Keys")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #F59E0B;")
        header_h.addWidget(lbl)
        header_h.addStretch()

        layout.addLayout(header_h)

        self.table_qbank = QTableWidget()
        self.table_qbank.setColumnCount(5)
        self.table_qbank.setHorizontalHeaderLabels(["Subject", "Unit", "Question", "Difficulty", "Marks"])
        self.table_qbank.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_qbank.setStyleSheet("""
            QTableWidget { background-color: #1F2937; color: white; gridline-color: #374151; font-size: 13px; }
            QHeaderView::section { background-color: #0F172A; color: #F59E0B; font-weight: bold; }
        """)
        self.table_qbank.itemSelectionChanged.connect(self._on_question_selected)
        layout.addWidget(self.table_qbank)

        # Question Detail Box
        self.txt_qdetail = QTextEdit()
        self.txt_qdetail.setReadOnly(True)
        self.txt_qdetail.setPlaceholderText("Select a question above to view full question and model answer key...")
        self.txt_qdetail.setStyleSheet("background-color: #1E293B; color: #34D399; font-family: Consolas; font-size: 13px; max-height: 120px;")
        layout.addWidget(self.txt_qdetail)

        if self.role == "faculty":
            qform_frame = QFrame()
            qform_frame.setStyleSheet("background-color: #1E293B; border-radius: 8px; padding: 10px;")
            qform_layout = QVBoxLayout(qform_frame)

            qform_title = QLabel("Add Question to Bank")
            qform_title.setStyleSheet("font-weight: bold; color: #60A5FA;")
            qform_layout.addWidget(qform_title)

            qh = QHBoxLayout()
            self.combo_q_subject = QComboBox()
            for s in self.subjects:
                self.combo_q_subject.addItem(f"{s[1]} - {s[2]}", s[0])
            self.combo_q_subject.setStyleSheet("background-color: #374151; color: white; padding: 6px;")

            self.combo_q_unit = QComboBox()
            for u in range(1, 6):
                self.combo_q_unit.addItem(f"Unit {u}", u)
            self.combo_q_unit.setStyleSheet("background-color: #374151; color: white; padding: 6px;")

            self.combo_q_diff = QComboBox()
            self.combo_q_diff.addItems(["Easy", "Medium", "Hard"])
            self.combo_q_diff.setStyleSheet("background-color: #374151; color: white; padding: 6px;")

            qh.addWidget(self.combo_q_subject)
            qh.addWidget(self.combo_q_unit)
            qh.addWidget(self.combo_q_diff)
            qform_layout.addLayout(qh)

            self.input_question = QLineEdit()
            self.input_question.setPlaceholderText("Question text...")
            self.input_question.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            self.input_answer = QTextEdit()
            self.input_answer.setPlaceholderText("Model Answer Key / Solution...")
            self.input_answer.setMaximumHeight(60)
            self.input_answer.setStyleSheet("background-color: #374151; color: white; padding: 8px;")

            btn_add_q = QPushButton("Add Question to Bank")
            btn_add_q.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
            btn_add_q.clicked.connect(self._add_question)

            qform_layout.addWidget(self.input_question)
            qform_layout.addWidget(self.input_answer)
            qform_layout.addWidget(btn_add_q)

            layout.addWidget(qform_frame)

        self.load_qbank()
        return page

    def load_notes(self):
        notes = get_notes()
        self.table_notes.setRowCount(len(notes))
        for idx, n in enumerate(notes):
            # n: (id, code, name, unit_number, title, file_path, created_at)
            self.table_notes.setItem(idx, 0, QTableWidgetItem(str(n[0])))
            self.table_notes.setItem(idx, 1, QTableWidgetItem(f"{n[1]} ({n[2]})"))
            self.table_notes.setItem(idx, 2, QTableWidgetItem(f"Unit {n[3]}"))
            self.table_notes.setItem(idx, 3, QTableWidgetItem(n[4]))
            self.table_notes.setItem(idx, 4, QTableWidgetItem(n[5]))

    def load_qbank(self):
        qitems = get_question_banks()
        self.table_qbank.setRowCount(len(qitems))
        for idx, q in enumerate(qitems):
            # q: (id, code, name, unit_number, question, answer_key, difficulty, marks)
            self.table_qbank.setItem(idx, 0, QTableWidgetItem(f"{q[1]} - {q[2]}"))
            self.table_qbank.setItem(idx, 1, QTableWidgetItem(f"Unit {q[3]}"))
            self.table_qbank.setItem(idx, 2, QTableWidgetItem(q[4]))
            self.table_qbank.setItem(idx, 3, QTableWidgetItem(q[6]))
            self.table_qbank.setItem(idx, 4, QTableWidgetItem(f"{q[7]} Marks"))
            self.table_qbank.item(idx, 0).setData(Qt.UserRole, q)

    def _on_question_selected(self):
        selected = self.table_qbank.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        q_data = self.table_qbank.item(row, 0).data(Qt.UserRole)
        if q_data:
            self.txt_qdetail.setPlainText(f"Question (Unit {q_data[3]}): {q_data[4]}\n\nModel Answer Key:\n{q_data[5]}")

    def _browse_note_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select PDF or Document File", "", "Documents (*.pdf *.txt *.md);;All Files (*.*)")
        if fname:
            self.input_note_filepath.setText(fname)

    def _upload_and_index_note(self):
        subject_id = self.combo_note_subject.currentData()
        unit = self.combo_unit.currentData()
        title = self.input_note_title.text().strip()
        filepath = self.input_note_filepath.text().strip()

        if not title or not filepath:
            QMessageBox.warning(self, "Warning", "Please provide title and file path.")
            return

        add_note(subject_id, title, filepath, unit_number=unit, uploaded_by=self.user[0])
        # Index into RAG
        rag_engine.ingest_file(title, filepath, subject_id)

        QMessageBox.information(self, "Success", "Document uploaded and indexed into AI RAG Engine successfully!")
        self.input_note_title.clear()
        self.input_note_filepath.clear()
        self.load_notes()

    def _add_question(self):
        subject_id = self.combo_q_subject.currentData()
        unit = self.combo_q_unit.currentData()
        diff = self.combo_q_diff.currentText()
        q_text = self.input_question.text().strip()
        ans_text = self.input_answer.toPlainText().strip()

        if not q_text or not ans_text:
            QMessageBox.warning(self, "Warning", "Please provide both question text and model answer.")
            return

        add_question_bank_item(subject_id, unit, q_text, ans_text, difficulty=diff, marks=5)
        QMessageBox.information(self, "Success", "Question added to bank successfully!")
        self.input_question.clear()
        self.input_answer.clear()
        self.load_qbank()
