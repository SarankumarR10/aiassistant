import os
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QTabWidget,
    QListWidget, QFrame, QSpinBox, QScrollArea, QStackedWidget
)
from PySide6.QtCore import Qt, QUrl, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QDesktopServices
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from database.database import (
    get_subjects,
    get_notes,
    get_academic_classes,
    get_question_banks,
    add_question_bank_item,
    delete_course_document,
)
from ai.rag_engine import rag_engine
from gui.theme import POSITIVUS_QSS, create_section_header
from storage.local_storage import storage_service

class NotesAndQuestionBankWidget(QWidget):
    """
    Unit Notes, Lab Manuals, and Model Question Bank Browser Widget.
    """
    def __init__(self, user, role: str = "faculty"):
        super().__init__()
        self.user = user
        self.role = role
        self.classes = get_academic_classes(faculty_id=user[0]) if role == "faculty" else get_academic_classes(student_user_id=user[0])
        self.class_labels = {row[0]: f"{row[1]} · Year {row[2]} · Section {row[3]} · {row[4]}" for row in self.classes}
        self.subjects = get_subjects(faculty_id=user[0]) if role == "faculty" else get_subjects(student_user_id=user[0])
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

        if self.role == "faculty":
            self.delete_note_button = QPushButton("Delete Selected Document")
            self.delete_note_button.setProperty("class", "danger")
            self.delete_note_button.setEnabled(False)
            self.delete_note_button.clicked.connect(self._delete_selected_note)
            layout.addWidget(self.delete_note_button, 0, Qt.AlignRight)

        self.table_notes = QTableWidget()
        self.table_notes.setColumnCount(6)
        self.table_notes.setHorizontalHeaderLabels(["ID", "Subject", "Class", "Unit #", "Title", "File"])
        self.table_notes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_notes.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_notes.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_notes.itemSelectionChanged.connect(self._preview_selected_note)
        self.table_notes.setMinimumHeight(220)
        layout.addWidget(self.table_notes)

        preview_header = QHBoxLayout()
        preview_title = QLabel("Selected Material")
        preview_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #26323B;")
        preview_header.addWidget(preview_title)
        preview_header.addStretch()
        self.open_material_button = QPushButton("Open Original File")
        self.open_material_button.setProperty("class", "outline")
        self.open_material_button.setEnabled(False)
        self.open_material_button.clicked.connect(self._open_selected_note)
        preview_header.addWidget(self.open_material_button)
        layout.addLayout(preview_header)

        self.preview_stack = QStackedWidget()
        self.preview_placeholder = QLabel("Select an uploaded material to view it here.")
        self.preview_placeholder.setAlignment(Qt.AlignCenter)
        self.preview_placeholder.setStyleSheet(
            "color: #687782; background: #FFFFFF; border: 1px solid #DCE2E7; "
            "border-radius: 8px; padding: 24px;"
        )
        self.note_preview = QTextEdit()
        self.note_preview.setReadOnly(True)
        self.note_preview.setPlaceholderText("Text and Markdown materials appear here.")
        self.note_preview.setMinimumHeight(360)
        self.pdf_document = QPdfDocument(self)
        self.pdf_buffer = QBuffer(self)
        self.pdf_data = QByteArray()
        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.setMinimumHeight(420)
        self.pdf_status = QLabel("Loading PDF preview…")
        self.pdf_status.setAlignment(Qt.AlignCenter)
        self.pdf_status.setStyleSheet("color: #687782; background: #FFFFFF; padding: 24px;")
        self.preview_stack.addWidget(self.preview_placeholder)
        self.preview_stack.addWidget(self.note_preview)
        self.preview_stack.addWidget(self.pdf_view)
        self.preview_stack.addWidget(self.pdf_status)
        self.preview_stack.setCurrentWidget(self.preview_placeholder)
        self.pdf_document.statusChanged.connect(self._update_pdf_preview)
        layout.addWidget(self.preview_stack, 1)

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
            self.combo_note_class = QComboBox()
            for class_row in self.classes:
                self.combo_note_class.addItem(self.class_labels[class_row[0]], class_row[0])
            self.combo_note_class.currentIndexChanged.connect(self._load_note_subjects)
            self.combo_note_subject = QComboBox()
            self._load_note_subjects()

            self.combo_unit = QComboBox()
            for u in range(1, 6):
                self.combo_unit.addItem(f"Unit {u}", u)

            h1.addWidget(self.combo_note_class)
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

            btn_upload = QPushButton("Upload Course Material")
            btn_upload.setCursor(Qt.PointingHandCursor)
            btn_upload.setProperty("class", "secondary")
            btn_upload.clicked.connect(self._upload_and_index_note)
            form_layout.addWidget(btn_upload)

            layout.addWidget(form_frame)

        self.load_notes()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidget(page)
        return scroll_area

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
        self.qbank_class_filter = QComboBox()
        self.qbank_class_filter.addItem("All assigned classes", None)
        if self.role == "faculty":
            for class_row in self.classes:
                self.qbank_class_filter.addItem(self.class_labels[class_row[0]], class_row[0])
        self.qbank_unit_filter = QComboBox()
        self.qbank_unit_filter.addItem("All units", None)
        for unit in range(1, 6):
            self.qbank_unit_filter.addItem(f"Unit {unit}", unit)
        self.qbank_source_filter = QComboBox()
        self.qbank_source_filter.addItem("All sources", None)
        self.qbank_source_filter.addItem("Model questions", "Model")
        self.qbank_source_filter.addItem("Previous-year questions", "Previous Year")
        filters.addWidget(self.qbank_search, 1)
        if self.role == "faculty":
            filters.addWidget(self.qbank_class_filter)
        filters.addWidget(self.qbank_subject_filter)
        filters.addWidget(self.qbank_unit_filter)
        filters.addWidget(self.qbank_source_filter)
        for control in (self.qbank_search, self.qbank_subject_filter,
                        self.qbank_unit_filter, self.qbank_source_filter,
                        *([self.qbank_class_filter] if self.role == "faculty" else [])):
            signal = control.textChanged if isinstance(control, QLineEdit) else control.currentIndexChanged
            signal.connect(self._filter_qbank)
        layout.addLayout(filters)

        self.table_qbank = QTableWidget()
        self.table_qbank.setColumnCount(8)
        self.table_qbank.setHorizontalHeaderLabels(["Subject", "Class", "Unit", "Source", "Year", "Question", "Difficulty", "Marks"])
        self.table_qbank.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_qbank.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
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
            self.combo_q_class = QComboBox()
            for class_row in self.classes:
                self.combo_q_class.addItem(self.class_labels[class_row[0]], class_row[0])
            self.combo_q_class.currentIndexChanged.connect(self._load_question_subjects)
            self.combo_q_subject = QComboBox()
            self._load_question_subjects()

            self.combo_q_unit = QComboBox()
            for u in range(1, 6):
                self.combo_q_unit.addItem(f"Unit {u}", u)

            self.combo_q_diff = QComboBox()
            self.combo_q_diff.addItems(["Easy", "Medium", "Hard"])

            qh.addWidget(self.combo_q_class)
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
        if self.role == "faculty":
            notes = get_notes(faculty_id=self.user[0], class_id=getattr(self, "combo_note_class", None).currentData()
                              if hasattr(self, "combo_note_class") else None)
        else:
            notes = get_notes(student_user_id=self.user[0])
        self.current_notes = notes
        self.table_notes.setRowCount(len(notes))
        for row, n in enumerate(notes):
            self.table_notes.setItem(row, 0, QTableWidgetItem(str(n[0])))
            self.table_notes.setItem(row, 1, QTableWidgetItem(f"{n[1]} - {n[2]}"))
            self.table_notes.setItem(row, 2, QTableWidgetItem(self.class_labels.get(n[7], "All classes") if n[7] else "All classes"))
            self.table_notes.setItem(row, 3, QTableWidgetItem(f"Unit {n[3]}"))
            self.table_notes.setItem(row, 4, QTableWidgetItem(str(n[4])))
            self.table_notes.setItem(row, 5, QTableWidgetItem(storage_service.file_name(n[5])))

    def _load_note_subjects(self, *_):
        if self.role != "faculty" or not hasattr(self, "combo_note_subject"):
            return
        self.combo_note_subject.clear()
        class_id = self.combo_note_class.currentData()
        if class_id is None:
            return
        for subject in get_subjects(faculty_id=self.user[0], class_id=int(class_id)):
            self.combo_note_subject.addItem(f"{subject[1]} - {subject[2]}", subject[0])

    def _load_question_subjects(self, *_):
        if self.role != "faculty" or not hasattr(self, "combo_q_subject"):
            return
        self.combo_q_subject.clear()
        class_id = self.combo_q_class.currentData()
        if class_id is None:
            return
        for subject in get_subjects(faculty_id=self.user[0], class_id=int(class_id)):
            self.combo_q_subject.addItem(f"{subject[1]} - {subject[2]}", subject[0])

    def _preview_selected_note(self):
        row = self.table_notes.currentRow()
        if row < 0 or row >= len(getattr(self, "current_notes", [])):
            self.note_preview.clear()
            self._selected_note_path = None
            self._close_pdf_preview()
            self.preview_stack.setCurrentWidget(self.preview_placeholder)
            self.open_material_button.setEnabled(False)
            if hasattr(self, "delete_note_button"):
                self.delete_note_button.setEnabled(False)
            return
        if hasattr(self, "delete_note_button"):
            self.delete_note_button.setEnabled(True)
        note = self.current_notes[row]
        title, reference = note[4], note[5]
        try:
            path = storage_service.resolve(reference)
            if not os.path.isfile(path):
                raise FileNotFoundError("The original course file is no longer available.")
            self._selected_note_path = path
            self.open_material_button.setEnabled(True)
            if path.suffix.lower() == ".pdf":
                self.pdf_status.setText("Loading PDF preview…")
                self.preview_stack.setCurrentWidget(self.pdf_status)
                self._close_pdf_preview()
                self.pdf_data = QByteArray(path.read_bytes())
                self.pdf_buffer.setData(self.pdf_data)
                if not self.pdf_buffer.open(QIODevice.ReadOnly):
                    raise OSError("Could not open the uploaded PDF for preview.")
                self.pdf_view.setDocument(self.pdf_document)
                self.pdf_document.load(self.pdf_buffer)
                self._update_pdf_preview(self.pdf_document.status())
            else:
                self._close_pdf_preview()
                with open(path, "r", encoding="utf-8", errors="replace") as stream:
                    content = stream.read(500_000)
                self.note_preview.setPlainText(f"{title}\n\n{content[:500_000]}")
                self.preview_stack.setCurrentWidget(self.note_preview)
        except Exception as error:
            self.open_material_button.setEnabled(False)
            self.note_preview.setPlainText(f"{title}\n\nCould not preview this note.\n{error}")
            self.preview_stack.setCurrentWidget(self.note_preview)

    def _update_pdf_preview(self, status):
        if not getattr(self, "_selected_note_path", None):
            return
        if status == QPdfDocument.Status.Ready:
            self.preview_stack.setCurrentWidget(self.pdf_view)
        elif status == QPdfDocument.Status.Error:
            self.pdf_status.setText(
                "EduPilot could not render this PDF. Use Open Original File to view it in your PDF app."
            )
            self.preview_stack.setCurrentWidget(self.pdf_status)
        elif status == QPdfDocument.Status.Loading:
            self.pdf_status.setText("Loading PDF preview…")
            self.preview_stack.setCurrentWidget(self.pdf_status)

    def _close_pdf_preview(self):
        # Detach and unload the memory-backed PDF before opening another file
        # or deleting the selected material.
        self.pdf_view.setDocument(None)
        self.pdf_document.close()
        self.pdf_buffer.close()
        self.pdf_data.clear()

    def _open_selected_note(self):
        path = getattr(self, "_selected_note_path", None)
        if path is None or not os.path.isfile(path):
            QMessageBox.warning(self, "Material unavailable", "Select an uploaded file that is still available.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))):
            QMessageBox.warning(self, "Could not open material", "No application is available to open this file.")

    def _delete_selected_note(self):
        row = self.table_notes.currentRow()
        if row < 0 or row >= len(getattr(self, "current_notes", [])):
            return
        note = self.current_notes[row]
        answer = QMessageBox.question(
            self,
            "Delete course document",
            f"Delete '{note[4]}' and remove it from local search?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        self._selected_note_path = None
        self._close_pdf_preview()
        try:
            delete_course_document(note[0], self.user[0])
        except Exception as error:
            QMessageBox.critical(self, "Could not delete document", str(error))
            return
        self.note_preview.clear()
        self.preview_stack.setCurrentWidget(self.preview_placeholder)
        self.open_material_button.setEnabled(False)
        self.load_notes()
        QMessageBox.information(self, "Document deleted", "The document and its search index were removed.")

    def _browse_note_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Note or Manual File", "", "Course documents (*.pdf *.txt *.md)")
        if fname:
            self.input_note_filepath.setText(fname)

    def _upload_and_index_note(self):
        subject_id = self.combo_note_subject.currentData()
        class_id = self.combo_note_class.currentData()
        unit_num = self.combo_unit.currentData()
        title = self.input_note_title.text().strip()
        filepath = self.input_note_filepath.text().strip()

        if subject_id is None:
            QMessageBox.warning(self, "Choose a subject", "Add or select a subject before uploading course material.")
            return
        if not title:
            self.input_note_title.setFocus()
            QMessageBox.warning(self, "Title required", "Enter a title for this course document.")
            return
        if not filepath:
            self.input_note_filepath.setFocus()
            QMessageBox.warning(self, "Choose a file", "Browse to a PDF, TXT, or Markdown document first.")
            return

        upload_button = self.sender()
        if isinstance(upload_button, QPushButton):
            upload_button.setEnabled(False)
            upload_button.setText("Uploading…")
        try:
            rag_engine.ingest_file(title=title, file_path=filepath, subject_id=subject_id,
                                   uploaded_by=self.user[0], unit_number=unit_num, class_id=class_id)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Could not add document",
                f"The document was not added to the Knowledge Base.\n\n{error}",
            )
            return
        finally:
            if isinstance(upload_button, QPushButton):
                upload_button.setEnabled(True)
                upload_button.setText("Upload Course Material")
        QMessageBox.information(self, "Success", f"'{title}' was added to course notes.")

        self.input_note_title.clear()
        self.input_note_filepath.clear()
        self.load_notes()
        for row, note in enumerate(self.current_notes):
            if note[4] == title and note[8] == self.user[0]:
                self.table_notes.selectRow(row)
                self.table_notes.scrollToItem(self.table_notes.item(row, 4))
                break

    def load_qbank(self):
        if self.role == "faculty":
            class_id = getattr(self, "qbank_class_filter", None).currentData() if hasattr(self, "qbank_class_filter") else None
            q_items = get_question_banks(faculty_id=self.user[0], class_id=class_id)
        else:
            q_items = get_question_banks(student_user_id=self.user[0])
        self.current_qitems = q_items
        self._filter_qbank()

    def _filter_qbank(self, *_):
        if not hasattr(self, "table_qbank"):
            return
        subject = self.qbank_subject_filter.currentData()
        unit = self.qbank_unit_filter.currentData()
        source = self.qbank_source_filter.currentData()
        class_id = self.qbank_class_filter.currentData() if self.role == "faculty" else None
        query = self.qbank_search.text().casefold().strip()
        self.visible_qitems = [
            q for q in getattr(self, "current_qitems", [])
            if (subject is None or q[1] == subject)
            and (class_id is None or q[10] == class_id)
            and (unit is None or q[3] == unit)
            and (source is None or q[8] == source)
            and (not query or query in " ".join(str(value or "") for value in q[1:]).casefold())
        ]
        self.table_qbank.setRowCount(len(self.visible_qitems))
        for row, q in enumerate(self.visible_qitems):
            year = str(q[9]) if q[9] else "—"
            class_label = self.class_labels.get(q[10], "All classes") if q[10] else "All classes"
            values = (f"{q[1]} — {q[2]}", class_label, f"Unit {q[3]}", q[8], year,
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
                                   faculty_id=self.user[0], source_kind=source_kind, exam_year=exam_year,
                                   class_id=self.combo_q_class.currentData())
        except Exception as error:
            QMessageBox.critical(self, "Could not add question", str(error))
            return
        QMessageBox.information(self, "Success", "Question added to Question Bank successfully!")
        self.input_question.clear()
        self.input_answer.clear()
        self.load_qbank()
