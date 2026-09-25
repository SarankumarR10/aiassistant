import calendar
from datetime import date, timedelta
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QDateEdit,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QFileDialog
)
from PySide6.QtCore import QDate, Qt

from database.database import (
    get_students,
    get_subjects,
    save_attendance,
    get_attendance_session_records
)
from reports.report_generator import report_generator
from gui.theme import POSITIVUS_QSS, create_section_header


class AttendanceWindow(QWidget):

    def __init__(self, faculty_id):
        super().__init__()

        self.faculty_id = faculty_id
        self.students = []
        self.statuses = {}
        self.verification_methods = {}

        self.setWindowTitle(
            "EduPilot - Smart Attendance Taker"
        )

        self.resize(1050, 720)

        self.build_ui()
        self.load_data()

    # =========================================================
    # BUILD UI
    # =========================================================

    def build_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            28,
            24,
            28,
            24
        )

        # HEADER
        header = create_section_header("Attendance Register & Verification", "Faculty Attendance Taker")
        layout.addWidget(header)
        layout.addSpacing(16)

        # SUBJECT + DATE
        controls = QHBoxLayout()

        subject_label = QLabel("Subject:")
        subject_label.setStyleSheet("font-weight: 600; color: #0F172A;")

        self.subject_combo = QComboBox()
        self.subject_combo.setMinimumWidth(320)

        section_label = QLabel("Section:")
        self.section_combo = QComboBox()

        date_label = QLabel("Date:")
        date_label.setStyleSheet("font-weight: 600; color: #0F172A;")

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())

        controls.addWidget(subject_label)
        controls.addWidget(self.subject_combo)
        controls.addWidget(section_label)
        controls.addWidget(self.section_combo)
        controls.addSpacing(20)
        controls.addWidget(date_label)
        controls.addWidget(self.date_edit)
        controls.addStretch()

        layout.addLayout(controls)
        layout.addSpacing(16)

        # ACTION BUTTONS
        attendance_buttons = QHBoxLayout()

        mark_present = QPushButton("Mark All Present")
        mark_present.setCursor(Qt.PointingHandCursor)
        mark_present.setProperty("class", "outline")
        mark_present.clicked.connect(self.mark_all_present)

        mark_absent = QPushButton("Mark All Absent")
        mark_absent.setCursor(Qt.PointingHandCursor)
        mark_absent.setProperty("class", "outline")
        mark_absent.clicked.connect(self.mark_all_absent)

        face_btn = QPushButton("Face attendance unavailable")
        face_btn.setCursor(Qt.PointingHandCursor)
        face_btn.setEnabled(False)
        face_btn.setToolTip("Face detection cannot verify a student's identity. Use manual or QR attendance.")

        qr_btn = QPushButton("Generate QR Attendance")
        qr_btn.setCursor(Qt.PointingHandCursor)
        qr_btn.setProperty("class", "outline")
        qr_btn.clicked.connect(self.start_qr_attendance)

        voice_btn = QPushButton("Voice Backup")
        voice_btn.setCursor(Qt.PointingHandCursor)
        voice_btn.setProperty("class", "outline")
        voice_btn.clicked.connect(self.start_voice_attendance)

        attendance_buttons.addWidget(mark_present)
        attendance_buttons.addWidget(mark_absent)
        attendance_buttons.addWidget(face_btn)
        attendance_buttons.addWidget(qr_btn)
        attendance_buttons.addWidget(voice_btn)
        attendance_buttons.addStretch()
        layout.addLayout(attendance_buttons)

        report_buttons = QHBoxLayout()
        self.report_period = QComboBox()
        self.report_period.addItems(["All dates", "Selected day", "Selected week", "Selected month"])
        report_buttons.addWidget(QLabel("Report period:"))
        report_buttons.addWidget(self.report_period)
        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.setCursor(Qt.PointingHandCursor)
        export_csv_btn.setProperty("class", "outline")
        export_csv_btn.clicked.connect(self.export_csv)

        export_html_btn = QPushButton("Export Report")
        export_html_btn.setCursor(Qt.PointingHandCursor)
        export_html_btn.setProperty("class", "outline")
        export_html_btn.clicked.connect(self.export_html)

        export_excel_btn = QPushButton("Export Excel")
        export_excel_btn.setProperty("class", "outline")
        export_excel_btn.clicked.connect(self.export_excel)

        export_pdf_btn = QPushButton("Export PDF")
        export_pdf_btn.setProperty("class", "outline")
        export_pdf_btn.clicked.connect(self.export_pdf)

        save_button = QPushButton("Save Attendance")
        save_button.setCursor(Qt.PointingHandCursor)
        save_button.setProperty("class", "secondary")
        save_button.clicked.connect(self.save)

        report_buttons.addWidget(export_csv_btn)
        report_buttons.addWidget(export_excel_btn)
        report_buttons.addWidget(export_html_btn)
        report_buttons.addWidget(export_pdf_btn)
        report_buttons.addWidget(save_button)
        report_buttons.addStretch()

        layout.addLayout(report_buttons)
        layout.addSpacing(16)

        # ATTENDANCE TABLE
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Roll Number",
            "Student Name",
            "Status",
            "Action"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.table)
        self.subject_combo.currentIndexChanged.connect(self._load_existing_attendance)
        self.date_edit.dateChanged.connect(self._load_existing_attendance)
        self.section_combo.currentIndexChanged.connect(self._load_section_students)

    def load_data(self):
        all_students = get_students()
        subjects = get_subjects()

        self.section_combo.blockSignals(True)
        self.section_combo.clear()
        self.section_combo.addItems(sorted({str(student[5]) for student in all_students}))
        self.section_combo.blockSignals(False)

        self.subject_combo.clear()
        for subject_id, code, name in subjects:
            self.subject_combo.addItem(f"{code} - {name}", subject_id)

        self._load_section_students()

    def _load_section_students(self, *_):
        section = self.section_combo.currentText()
        self.students = get_students(section) if section else []
        self.table.setRowCount(len(self.students))
        self.statuses.clear()
        self.verification_methods.clear()

        for row, student in enumerate(self.students):
            student_id = student[0]
            roll = student[1]
            name = student[2]

            self.statuses[student_id] = "Unmarked"
            self.verification_methods[student_id] = "manual"
            self.table.setItem(row, 0, QTableWidgetItem(str(roll)))
            self.table.setItem(row, 1, QTableWidgetItem(str(name)))

            status_item = QTableWidgetItem("Unmarked")
            self.table.setItem(row, 2, status_item)

            toggle = QPushButton("Toggle")
            toggle.setCursor(Qt.PointingHandCursor)
            toggle.setProperty("class", "outline")
            toggle.clicked.connect(lambda checked=False, sid=student_id, r=row: self.toggle_status(sid, r))

            self.table.setCellWidget(row, 3, toggle)
        self._load_existing_attendance()

    def _load_existing_attendance(self, *_):
        subject_id = self.subject_combo.currentData()
        if not subject_id:
            return
        qdate = self.date_edit.date()
        date_str = f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"
        existing = get_attendance_session_records(subject_id, date_str, self.section_combo.currentText())
        for row, student in enumerate(self.students):
            student_id = student[0]
            saved = existing.get(student_id)
            status, method = saved if saved else ("Unmarked", "manual")
            self.statuses[student_id] = status
            self.verification_methods[student_id] = method
            item = self.table.item(row, 2)
            if item:
                item.setText(status)

    def toggle_status(self, student_id, row):
        current = self.statuses.get(student_id, "Unmarked")
        new_status = "Present" if current in ("Absent", "Unmarked") else "Absent"
        self.statuses[student_id] = new_status
        self.verification_methods[student_id] = "manual"
        item = self.table.item(row, 2)
        if item:
            item.setText(new_status)

    def mark_all_present(self):
        for row, student in enumerate(self.students):
            student_id = student[0]
            self.statuses[student_id] = "Present"
            self.verification_methods[student_id] = "manual"
            item = self.table.item(row, 2)
            if item:
                item.setText("Present")

    def mark_all_absent(self):
        for row, student in enumerate(self.students):
            student_id = student[0]
            self.statuses[student_id] = "Absent"
            self.verification_methods[student_id] = "manual"
            item = self.table.item(row, 2)
            if item:
                item.setText("Absent")

    def save(self):
        subject_id = self.subject_combo.currentData()
        qdate = self.date_edit.date()
        date_str = f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"

        if not subject_id:
            QMessageBox.warning(self, "Attendance", "Please select a subject.")
            return
        if not self.students or any(status not in ("Present", "Absent") for status in self.statuses.values()):
            QMessageBox.warning(self, "Attendance", "Mark every student Present or Absent before saving.")
            return

        try:
            save_attendance(
                records={student_id: (status, self.verification_methods.get(student_id, "manual"))
                         for student_id, status in self.statuses.items()},
                subject_id=subject_id,
                attendance_date=date_str,
                faculty_id=self.faculty_id,
                section=self.section_combo.currentText(),
            )
            QMessageBox.information(self, "Attendance", "Attendance recorded successfully into database.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save attendance: {e}")

    def export_csv(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Attendance CSV", "Attendance_Report.csv", "CSV Files (*.csv)")
        if fname:
            try:
                report_generator.export_attendance_csv(fname, **self._report_filters())
                QMessageBox.information(self, "Success", f"Attendance CSV saved to:\n{fname}")
            except Exception as error:
                QMessageBox.critical(self, "Could not export CSV", str(error))

    def export_html(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Attendance Report HTML", "Attendance_Summary.html", "HTML Files (*.html)")
        if fname:
            try:
                report_generator.export_attendance_html_report(fname, **self._report_filters())
                QMessageBox.information(self, "Success", f"Attendance HTML report saved to:\n{fname}")
            except Exception as error:
                QMessageBox.critical(self, "Could not export HTML", str(error))

    def export_excel(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Attendance Workbook", "Attendance_Report.xlsx", "Excel Workbooks (*.xlsx)")
        if fname:
            try:
                report_generator.export_attendance_xlsx(fname, **self._report_filters())
                QMessageBox.information(self, "Success", f"Attendance workbook saved to:\n{fname}")
            except Exception as error:
                QMessageBox.critical(self, "Could not export workbook", str(error))

    def export_pdf(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Attendance PDF", "Attendance_Report.pdf", "PDF Files (*.pdf)")
        if fname:
            try:
                if not report_generator.export_attendance_pdf_report(fname, **self._report_filters()):
                    raise RuntimeError("The PDF report could not be created.")
                QMessageBox.information(self, "Success", f"Attendance PDF saved to:\n{fname}")
            except Exception as error:
                QMessageBox.critical(self, "Could not export PDF", str(error))

    def _report_filters(self):
        selected = self.date_edit.date()
        anchor = date(selected.year(), selected.month(), selected.day())
        period = self.report_period.currentText()
        start_date = end_date = None
        if period == "Selected day":
            start_date = end_date = anchor
        elif period == "Selected week":
            start_date = anchor - timedelta(days=anchor.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == "Selected month":
            start_date = anchor.replace(day=1)
            end_date = anchor.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])
        return {
            "subject_id": self.subject_combo.currentData(),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "section": self.section_combo.currentText() or None,
        }

    def start_face_attendance(self):
        QMessageBox.information(self, "Face attendance unavailable",
            "Face detection is not identity verification. Face attendance will be enabled after consented student enrollment and identity matching are implemented.")

    def start_qr_attendance(self):
        from attendance.qr_attendance import QRAttendanceSystem
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QApplication
        from PySide6.QtGui import QPixmap

        subject_id = self.subject_combo.currentData()
        if not subject_id:
            QMessageBox.warning(self, "QR attendance", "Select a subject before opening a QR check-in.")
            return
        qdate = self.date_edit.date()
        date_str = f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"

        try:
            qr_sys = QRAttendanceSystem()
            token = qr_sys.generate_token(subject_id, date_str, self.faculty_id, self.section_combo.currentText())
        except Exception as error:
            QMessageBox.warning(self, "QR attendance", str(error))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Dynamic Classroom Session QR Code")
        dialog.setMinimumSize(440, 520)
        d_layout = QVBoxLayout(dialog)
        d_layout.setContentsMargins(24, 22, 24, 20)
        d_layout.setSpacing(12)

        lbl_title = QLabel("Session Attendance QR Token")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        d_layout.addWidget(lbl_title)

        qr_label = QLabel()
        qr_label.setFixedSize(252, 252)
        qr_label.setAlignment(Qt.AlignCenter)
        qr_label.setStyleSheet("background: #FFFFFF; border: 1px solid #DCE2E7; border-radius: 10px; padding: 10px;")
        d_layout.addWidget(qr_label, alignment=Qt.AlignHCenter)
        qr_status = QLabel()
        qr_status.setWordWrap(True)
        qr_status.setStyleSheet("color: #687782; font-size: 12px;")
        try:
            import io
            import qrcode
            image_bytes = io.BytesIO()
            qrcode.make(token).save(image_bytes, format="PNG")
            qr_image = QPixmap()
            if not qr_image.loadFromData(image_bytes.getvalue(), "PNG"):
                raise RuntimeError("Qt could not read the generated QR image.")
            qr_label.setPixmap(qr_image.scaled(228, 228, Qt.KeepAspectRatio, Qt.FastTransformation))
            qr_status.setText("Ready to scan. This QR code expires in 5 minutes.")
        except Exception as error:
            qr_label.setText("QR image unavailable")
            qr_status.setText(
                "The signed attendance code is still valid. To display a scannable QR, install the project requirements "
                "in the same Python environment used to launch EduPilot. "
                f"Details: {error}"
            )
        d_layout.addWidget(qr_status)

        lbl_token_title = QLabel("Manual check-in code")
        lbl_token_title.setStyleSheet("font-weight: 600; color: #26323B; margin-top: 2px;")
        d_layout.addWidget(lbl_token_title)
        lbl_token = QLabel(token)
        lbl_token.setWordWrap(True)
        lbl_token.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl_token.setStyleSheet("background: #F4F6F8; color: #26323B; font-family: Consolas, monospace; padding: 10px; border: 1px solid #DCE2E7; border-radius: 7px;")
        d_layout.addWidget(lbl_token)
        copy_button = QPushButton("Copy Check-in Code")
        copy_button.setProperty("class", "outline")
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(token))
        d_layout.addWidget(copy_button)

        lbl_instr = QLabel("Students can scan the QR code or paste the copied code on their Attendance page.")
        lbl_instr.setWordWrap(True)
        lbl_instr.setStyleSheet("color: #64748B; font-size: 12px;")
        d_layout.addWidget(lbl_instr)

        btn_close = QPushButton("Close QR Session")
        btn_close.clicked.connect(dialog.accept)
        d_layout.addWidget(btn_close)

        dialog.exec()

    def start_voice_attendance(self):
        from attendance.voice_attendance import parse_roll_call_response, parse_voice_attendance_phrase
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
        from PySide6.QtCore import QTimer
        from gui.speech_worker import SpeechInputWorker
        from voice.speech_input import speech_input_status
        from voice.voice_engine import voice_engine

        dialog = QDialog(self)
        dialog.setWindowTitle("Voice Backup Attendance Marking")
        dialog.setMinimumSize(520, 360)
        d_layout = QVBoxLayout(dialog)

        lbl_title = QLabel("Speak or Enter Attendance Names and Statuses")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #0F172A;")
        d_layout.addWidget(lbl_title)

        input_voice = QLineEdit()
        input_voice.setPlaceholderText("e.g. 'Arun Kumar present, Bala Kumar absent' or 'Roll 1 present'")
        d_layout.addWidget(input_voice)

        ready, speech_message = speech_input_status()
        mic_row = QHBoxLayout()
        mic_status = QLabel(speech_message)
        mic_status.setWordWrap(True)
        mic_start = QPushButton("Start Microphone")
        mic_start.setProperty("class", "outline")
        mic_start.setEnabled(ready)
        mic_stop = QPushButton("Stop Listening")
        mic_stop.setProperty("class", "outline")
        mic_stop.setEnabled(False)
        mic_row.addWidget(mic_start)
        mic_row.addWidget(mic_stop)
        mic_row.addWidget(mic_status, 1)
        d_layout.addLayout(mic_row)

        guided_button = QPushButton("Start Guided Roll Call")
        guided_button.setProperty("class", "secondary")
        guided_button.setEnabled(ready and bool(self.students))
        guided_button.setToolTip(
            "Call each unmarked student and record a local spoken Present or Absent response."
            if ready else speech_message
        )
        d_layout.addWidget(guided_button)

        lbl_log = QLabel("Enter a multi-student phrase, or start guided roll call when offline speech is configured.")
        lbl_log.setWordWrap(True)
        lbl_log.setStyleSheet("color: #64748B; font-size: 12px;")
        d_layout.addWidget(lbl_log)

        active_worker = [None]
        mic_monitor = QTimer(dialog)
        mic_monitor.setInterval(200)
        roll_call_active = [False]
        roll_call_rows = []
        roll_call_position = [0]
        awaiting_response = [False]
        btn_proc = None

        def finish_roll_call(message):
            roll_call_active[0] = False
            input_voice.setReadOnly(False)
            if btn_proc:
                btn_proc.setEnabled(True)
            guided_button.setEnabled(speech_input_status()[0] and bool(self.students))
            lbl_log.setText(message)
            mic_status.setText(message)
            worker = active_worker[0]
            if worker and worker.isRunning():
                worker.request_stop()

        def call_next_student():
            if not roll_call_active[0]:
                return
            if roll_call_position[0] >= len(roll_call_rows):
                finish_roll_call("Guided roll call complete. Responses were recorded locally.")
                return
            row = roll_call_rows[roll_call_position[0]]
            name = str(self.students[row][2])
            input_voice.clear()
            awaiting_response[0] = True
            lbl_log.setText(f"Called {name}. Waiting for a clear Present or Absent response.")
            voice_engine.speak(f"Roll call. {name}.")

        def handle_guided_response(phrase):
            if not roll_call_active[0] or not awaiting_response[0]:
                return
            try:
                status = parse_roll_call_response(phrase)
            except ValueError as error:
                lbl_log.setText(str(error))
                voice_engine.speak("Please say either present or absent.")
                input_voice.clear()
                return
            if status is None:
                lbl_log.setText("I did not hear Present or Absent. Please try again.")
                voice_engine.speak("Please say present or absent.")
                input_voice.clear()
                return
            awaiting_response[0] = False
            row = roll_call_rows[roll_call_position[0]]
            student = self.students[row]
            self.statuses[student[0]] = status
            self.verification_methods[student[0]] = "voice"
            status_item = self.table.item(row, 2)
            if status_item:
                status_item.setText(status)
            roll_call_position[0] += 1
            QTimer.singleShot(250, call_next_student)

        def on_voice_text_changed(text):
            if roll_call_active[0] and text.strip():
                handle_guided_response(text.strip())

        input_voice.textChanged.connect(on_voice_text_changed)

        def check_mic_finished():
            worker = active_worker[0]
            if worker and not worker.isRunning():
                active_worker[0] = None
                mic_monitor.stop()
                mic_start.setEnabled(speech_input_status()[0])
                mic_stop.setEnabled(False)
                if mic_status.text().startswith(("Listening", "Stopping")):
                    mic_status.setText("Microphone stopped.")
                if roll_call_active[0]:
                    finish_roll_call("Microphone stopped before roll call finished. Completed responses are kept.")

        def start_mic():
            if active_worker[0] and active_worker[0].isRunning():
                return False
            ready, explanation = speech_input_status()
            if not ready:
                mic_status.setText(explanation)
                return False
            worker = SpeechInputWorker(dialog)
            worker.phrase_recognized.connect(input_voice.setText)
            worker.failed.connect(mic_status.setText)
            active_worker[0] = worker
            mic_status.setText("Listening offline; pause after speaking.")
            mic_start.setEnabled(False)
            mic_stop.setEnabled(True)
            worker.start()
            mic_monitor.start()
            return True

        def stop_mic():
            worker = active_worker[0]
            if roll_call_active[0]:
                roll_call_active[0] = False
                input_voice.setReadOnly(False)
                if btn_proc:
                    btn_proc.setEnabled(True)
                guided_button.setEnabled(speech_input_status()[0] and bool(self.students))
                lbl_log.setText("Guided roll call stopped. Completed responses are kept; remaining students are unchanged.")
            if worker and worker.isRunning():
                mic_status.setText("Stopping microphone…")
                mic_stop.setEnabled(False)
                worker.request_stop()

        mic_start.clicked.connect(start_mic)
        mic_stop.clicked.connect(stop_mic)
        mic_monitor.timeout.connect(check_mic_finished)

        def start_guided_roll_call():
            if not self.students:
                lbl_log.setText("Choose a section with enrolled students before starting roll call.")
                return
            if active_worker[0] and active_worker[0].isRunning():
                lbl_log.setText("Stop the current microphone session before starting guided roll call.")
                return
            ready, explanation = speech_input_status()
            if not ready:
                mic_status.setText(explanation)
                return
            roll_call_rows[:] = [
                row for row, student in enumerate(self.students)
                if self.statuses.get(student[0], "Unmarked") == "Unmarked"
            ]
            if not roll_call_rows:
                lbl_log.setText("Every student in this section is already marked.")
                return
            roll_call_position[0] = 0
            awaiting_response[0] = False
            roll_call_active[0] = True
            input_voice.setReadOnly(True)
            if btn_proc:
                btn_proc.setEnabled(False)
            guided_button.setEnabled(False)
            if not start_mic():
                roll_call_active[0] = False
                input_voice.setReadOnly(False)
                if btn_proc:
                    btn_proc.setEnabled(True)
                guided_button.setEnabled(speech_input_status()[0] and bool(self.students))
                return
            mic_status.setText("Guided roll call is listening offline. No audio is saved.")
            call_next_student()

        guided_button.clicked.connect(start_guided_roll_call)

        def process_phrase():
            text = input_voice.text()
            try:
                results = parse_voice_attendance_phrase(text, self.students)
            except ValueError as error:
                lbl_log.setText(str(error))
                return
            if results:
                count = 0
                unmatched = []
                for item in results:
                    roll = item["roll_number"]
                    status = item["status"]
                    for row, student in enumerate(self.students):
                        if student[1].upper() == roll:
                            self.statuses[student[0]] = status
                            self.verification_methods[student[0]] = "voice"
                            item_t = self.table.item(row, 2)
                            if item_t:
                                item_t.setText(status)
                            count += 1
                    if not any(student[1].upper() == roll for student in self.students):
                        unmatched.append(roll)
                suffix = f" Not in this section: {', '.join(unmatched)}." if unmatched else ""
                lbl_log.setText(f"Applied attendance to {count} student record(s).{suffix}")
            else:
                lbl_log.setText("No student names or roll numbers were recognized. Try: 'Arun Kumar present' or 'Roll 1 absent'.")

        btn_proc = QPushButton("Process Attendance Phrase")
        btn_proc.setProperty("class", "secondary")
        btn_proc.clicked.connect(process_phrase)
        d_layout.addWidget(btn_proc)

        btn_done = QPushButton("Done")
        btn_done.clicked.connect(dialog.accept)
        d_layout.addWidget(btn_done)

        dialog.exec()
        worker = active_worker[0]
        if worker and worker.isRunning():
            worker.request_stop()
            worker.wait()
