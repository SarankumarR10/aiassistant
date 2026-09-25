import os
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QTabWidget,
    QListWidget, QFrame, QSpinBox
)
from PySide6.QtCore import Qt
from database.database import (
    get_subjects,
    get_notes,
    get_question_banks,
    add_question_bank_item
)
from ai.rag_engine import rag_engine
from gui.theme import POSITIVUS_QSS, create_section_header

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
        self.setStyleSheet(POSITIVUS_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = create_section_header("Knowledge Base & Question Bank")
        layout.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self._build_notes_tab(), "Unit Notes && Reference Manuals")
        tabs.addTab(self._build_qbank_tab(), "Model Question Bank")

        layout.addWidget(tabs)

    def _build_notes_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel("Uploaded Lecture Notes & Reference Manuals")
        lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        layout.addWidget(lbl)

        self.table_notes = QTableWidget()
        self.table_notes.setColumnCount(5)
        self.table_notes.setHorizontalHeaderLabels(["ID", "Subject", "Unit #", "Title", "File Path"])
        self.table_notes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_notes.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_notes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_notes.itemSelectionChanged.connect(self._preview_selected_note)
        layout.addWidget(self.table_notes)
        self.note_preview = QTextEdit()
        self.note_preview.setReadOnly(True)
        self.note_preview.setPlaceholderText("Select a note to preview its contents.")
        self.note_preview.setMinimumHeight(180)
        layout.addWidget(self.note_preview)

        if self.role == "faculty":
            form_frame = QFrame()
            form_frame.setObjectName("surfaceCard")
            form_frame.setStyleSheet("""
                QFrame#surfaceCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                    padding: 14px;
                }
            """)
            form_layout = QVBoxLayout(form_frame)

            form_title = QLabel("Upload New Lecture Note / Manual PDF")
            form_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #0F172A;")
            form_layout.addWidget(form_title)

            h1 = QHBoxLayout()
            self.combo_note_subject = QComboBox()
            for s in self.subjects:
                self.combo_note_subject.addItem(f"{s[1]} - {s[2]}", s[0])

            self.combo_unit = QComboBox()
            for u in range(1, 6):
                self.combo_unit.addItem(f"Unit {u}", u)

            h1.addWidget(self.combo_note_subject)
            h1.addWidget(self.combo_unit)
            form_layout.addLayout(h1)

            self.input_note_title = QLineEdit()
            self.input_note_title.setPlaceholderText("Document Title (e.g., Unit 2 Normalization Notes)...")
            form_layout.addWidget(self.input_note_title)

            h2 = QHBoxLayout()
            self.input_note_filepath = QLineEdit()
            self.input_note_filepath.setPlaceholderText("File Path (.pdf, .txt, .md)...")

            btn_browse = QPushButton("Browse File")
            btn_browse.setCursor(Qt.PointingHandCursor)
            btn_browse.setProperty("class", "outline")
            btn_browse.clicked.connect(self._browse_note_file)

            h2.addWidget(self.input_note_filepath)
            h2.addWidget(btn_browse)
            form_layout.addLayout(h2)

            btn_upload = QPushButton("Upload && Index into Local RAG Engine")
            btn_upload.setCursor(Qt.PointingHandCursor)
            btn_upload.setProperty("class", "secondary")
            btn_upload.clicked.connect(self._upload_and_index_note)
            form_layout.addWidget(btn_upload)

            layout.addWidget(form_frame)

        self.load_notes()
        return page

    def _build_qbank_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel("Unit-wise Model Question Bank & Answer Keys")
        lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        layout.addWidget(lbl)

        filters = QHBoxLayout()
        self.qbank_search = QLineEdit()
        self.qbank_search.setPlaceholderText("Search questions and answer keys…")
        self.qbank_subject_filter = QComboBox()
        self.qbank_subject_filter.addItem("All subjects", None)
        for subject in self.subjects:
            self.qbank_subject_filter.addItem(f"{subject[1]} — {subject[2]}", subject[1])
        self.qbank_unit_filter = QComboBox()
        self.qbank_unit_filter.addItem("All units", None)
        for unit in range(1, 6):
            self.qbank_unit_filter.addItem(f"Unit {unit}", unit)
        self.qbank_source_filter = QComboBox()
        self.qbank_source_filter.addItem("All sources", None)
        self.qbank_source_filter.addItem("Model questions", "Model")
        self.qbank_source_filter.addItem("Previous-year questions", "Previous Year")
        filters.addWidget(self.qbank_search, 1)
        filters.addWidget(self.qbank_subject_filter)
        filters.addWidget(self.qbank_unit_filter)
        filters.addWidget(self.qbank_source_filter)
        for control in (self.qbank_search, self.qbank_subject_filter,
                        self.qbank_unit_filter, self.qbank_source_filter):
            signal = control.textChanged if isinstance(control, QLineEdit) else control.currentIndexChanged
            signal.connect(self._filter_qbank)
        layout.addLayout(filters)

        self.table_qbank = QTableWidget()
        self.table_qbank.setColumnCount(7)
        self.table_qbank.setHorizontalHeaderLabels(["Subject", "Unit", "Source", "Year", "Question", "Difficulty", "Marks"])
        self.table_qbank.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_qbank.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table_qbank.itemSelectionChanged.connect(self._on_question_selected)
        layout.addWidget(self.table_qbank)

        # Question Detail Box
        self.txt_qdetail = QTextEdit()
        self.txt_qdetail.setReadOnly(True)
        self.txt_qdetail.setPlaceholderText("Select a question above to view full question and model answer key...")
        self.txt_qdetail.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #26323B;
                font-family: 'Consolas', monospace;
                font-size: 13px;
            }
        """)
        self.txt_qdetail.setMinimumHeight(150)
        layout.addWidget(self.txt_qdetail)

        if self.role == "faculty":
            qform_frame = QFrame()
            qform_frame.setObjectName("surfaceCard")
            qform_frame.setStyleSheet("""
                QFrame#surfaceCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                    padding: 14px;
                }
            """)
            qform_layout = QVBoxLayout(qform_frame)

            qform_title = QLabel("Add Question to Bank")
            qform_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #0F172A;")
            qform_layout.addWidget(qform_title)

            qh = QHBoxLayout()
            self.combo_q_subject = QComboBox()
            for s in self.subjects:
                self.combo_q_subject.addItem(f"{s[1]} - {s[2]}", s[0])

            self.combo_q_unit = QComboBox()
            for u in range(1, 6):
                self.combo_q_unit.addItem(f"Unit {u}", u)

            self.combo_q_diff = QComboBox()
            self.combo_q_diff.addItems(["Easy", "Medium", "Hard"])

            qh.addWidget(self.combo_q_subject)
            qh.addWidget(self.combo_q_unit)
            qh.addWidget(self.combo_q_diff)
            qform_layout.addLayout(qh)

            qh_source = QHBoxLayout()
            self.combo_q_source = QComboBox()
            self.combo_q_source.addItems(["Model", "Previous Year"])
            self.input_q_exam_year = QSpinBox()
            self.input_q_exam_year.setRange(2000, date.today().year)
            self.input_q_exam_year.setValue(date.today().year - 1)
            self.input_q_exam_year.setEnabled(False)
            self.combo_q_source.currentTextChanged.connect(
                lambda source: self.input_q_exam_year.setEnabled(source == "Previous Year")
            )
            qh_source.addWidget(QLabel("Question type:"))
            qh_source.addWidget(self.combo_q_source)
            qh_source.addWidget(QLabel("Exam year:"))
            qh_source.addWidget(self.input_q_exam_year)
            qh_source.addStretch()
            qform_layout.addLayout(qh_source)

            self.input_question = QLineEdit()
            self.input_question.setPlaceholderText("Question text...")

            self.input_answer = QTextEdit()
            self.input_answer.setPlaceholderText("Model Answer Key / Solution...")
            self.input_answer.setMaximumHeight(60)

            btn_add_q = QPushButton("Add Question to Bank")
            btn_add_q.setCursor(Qt.PointingHandCursor)
            btn_add_q.clicked.connect(self._add_question)

            qform_layout.addWidget(self.input_question)
            qform_layout.addWidget(self.input_answer)
            qform_layout.addWidget(btn_add_q)

            layout.addWidget(qform_frame)

        self.load_qbank()
        return page

    def load_notes(self):
        notes = get_notes()
        self.current_notes = notes
        self.table_notes.setRowCount(len(notes))
        for row, n in enumerate(notes):
            self.table_notes.setItem(row, 0, QTableWidgetItem(str(n[0])))
            self.table_notes.setItem(row, 1, QTableWidgetItem(f"{n[1]} - {n[2]}"))
            self.table_notes.setItem(row, 2, QTableWidgetItem(f"Unit {n[3]}"))
            self.table_notes.setItem(row, 3, QTableWidgetItem(str(n[4])))
            self.table_notes.setItem(row, 4, QTableWidgetItem(str(n[5])))

    def _preview_selected_note(self):
        row = self.table_notes.currentRow()
        if row < 0 or row >= len(getattr(self, "current_notes", [])):
            return
        note = self.current_notes[row]
        title, path = note[4], note[5]
        try:
            if not os.path.isfile(path):
                raise FileNotFoundError(f"The source file is not available at: {path}")
            if os.path.splitext(path)[1].lower() == ".pdf":
                from pypdf import PdfReader
                content = "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
                if not content.strip():
                    content = "This PDF has no extractable text. It may contain scanned pages."
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as stream:
                    content = stream.read(500_000)
            self.note_preview.setPlainText(f"{title}\n\n{content[:500_000]}")
        except Exception as error:
            self.note_preview.setPlainText(f"{title}\n\nCould not preview this note.\n{error}")

    def _browse_note_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Note or Manual File", "", "Course documents (*.pdf *.txt *.md)")
        if fname:
            self.input_note_filepath.setText(fname)

    def _upload_and_index_note(self):
        subject_id = self.combo_note_subject.currentData()
        unit_num = self.combo_unit.currentData()
        title = self.input_note_title.text().strip()
        filepath = self.input_note_filepath.text().strip()

        if not title or not filepath:
            QMessageBox.warning(self, "Warning", "Please enter Title and File Path.")
            return

        try:
            rag_engine.ingest_file(title=title, file_path=filepath, subject_id=subject_id,
                                   uploaded_by=self.user[0], unit_number=unit_num)
        except Exception as error:
            QMessageBox.critical(self, "Could not add document", str(error))
            return
        QMessageBox.information(self, "Success", f"'{title}' was indexed and added to course notes.")

        self.input_note_title.clear()
        self.input_note_filepath.clear()
        self.load_notes()

    def load_qbank(self):
        q_items = get_question_banks()
        self.current_qitems = q_items
        self._filter_qbank()

    def _filter_qbank(self, *_):
        if not hasattr(self, "table_qbank"):
            return
        subject = self.qbank_subject_filter.currentData()
        unit = self.qbank_unit_filter.currentData()
        source = self.qbank_source_filter.currentData()
        query = self.qbank_search.text().casefold().strip()
        self.visible_qitems = [
            q for q in getattr(self, "current_qitems", [])
            if (subject is None or q[1] == subject)
            and (unit is None or q[3] == unit)
            and (source is None or q[8] == source)
            and (not query or query in " ".join(str(value or "") for value in q[1:]).casefold())
        ]
        self.table_qbank.setRowCount(len(self.visible_qitems))
        for row, q in enumerate(self.visible_qitems):
            year = str(q[9]) if q[9] else "—"
            values = (f"{q[1]} — {q[2]}", f"Unit {q[3]}", q[8], year,
                      str(q[4]), str(q[6]), f"{q[7]} Marks")
            for column, value in enumerate(values):
                self.table_qbank.setItem(row, column, QTableWidgetItem(value))

    def _on_question_selected(self):
        selected = self.table_qbank.selectedItems()
        if not selected or not hasattr(self, 'visible_qitems'):
            return
        row = selected[0].row()
        if row >= len(self.visible_qitems):
            return
        q = self.visible_qitems[row]
        self.txt_qdetail.setPlainText(f"Question: {q[4]}\n\nModel Answer / Solution Key:\n{q[5]}")

    def _add_question(self):
        subject_id = self.combo_q_subject.currentData()
        unit_num = self.combo_q_unit.currentData()
        diff = self.combo_q_diff.currentText()
        source_kind = self.combo_q_source.currentText()
        exam_year = self.input_q_exam_year.value() if source_kind == "Previous Year" else None
        q_text = self.input_question.text().strip()
        ans_text = self.input_answer.toPlainText().strip()

        if not q_text:
            QMessageBox.warning(self, "Warning", "Question text is required.")
            return

        try:
            add_question_bank_item(subject_id, unit_num, q_text, ans_text, diff, 5,
                                   faculty_id=self.user[0], source_kind=source_kind, exam_year=exam_year)
        except Exception as error:
            QMessageBox.critical(self, "Could not add question", str(error))
            return
        QMessageBox.information(self, "Success", "Question added to Question Bank successfully!")
        self.input_question.clear()
        self.input_answer.clear()
        self.load_qbank()
