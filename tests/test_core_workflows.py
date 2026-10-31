"""Dependency-light tests for EduPilot's core local workflows."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import database.database as database
from ai.rag_engine import rag_engine
from voice.voice_engine import VoiceEngine, _normalize_voice_text
from voice.local_search import search_local_items
from voice.speech_input import _prepare_audio
from reports.report_generator import report_generator
from attendance.qr_attendance import QRAttendanceSystem
from storage.local_storage import STORAGE_PREFIX, storage_service


class CoreWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="edupilot-tests-", dir=Path.cwd())
        cls.root = Path(cls.temp.name)
        database.DB_PATH = cls.root / "test.sqlite3"
        database.LEGACY_DB_PATH = cls.root / "legacy.sqlite3"
        storage_service.root = cls.root / "uploads"
        database.initialize_database()
        cls.faculty_user_id = database.authenticate_user("faculty2", "Faculty123!")[0]
        cls.student_user_id = database.authenticate_user("student1", "Student123!")[0]
        connection = database.get_connection()
        try:
            cls.student_id = connection.execute(
                "SELECT id FROM students WHERE user_id = ?", (cls.student_user_id,)
            ).fetchone()[0]
            cls.class_id = connection.execute(
                "SELECT class_id FROM students WHERE id = ?", (cls.student_id,)
            ).fetchone()[0]
            cls.subject_id = connection.execute(
                "SELECT id FROM subjects WHERE code = 'CS303'"
            ).fetchone()[0]
        finally:
            connection.close()
        database.add_assignment(
            cls.subject_id, "Workflow Test Assignment", "Test content", date.today().isoformat(),
            faculty_id=cls.faculty_user_id, class_id=cls.class_id,
        )
        connection = database.get_connection()
        try:
            cls.assignment_id = connection.execute(
                "SELECT id FROM assignments WHERE title = 'Workflow Test Assignment'"
            ).fetchone()[0]
        finally:
            connection.close()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_database_initialization_is_idempotent_and_passwords_are_hashed(self):
        database.initialize_database()
        self.assertEqual(database.authenticate_user("faculty1", "Faculty123!")[2], "faculty")
        self.assertIsNone(database.authenticate_user("faculty1", "wrong-password"))
        connection = database.get_connection()
        try:
            password = connection.execute(
                "SELECT password FROM users WHERE username = 'faculty1'"
            ).fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            connection.close()
        self.assertTrue(password.startswith("pbkdf2_sha256$"))
        self.assertEqual(version, 4)
        with self.assertRaises(PermissionError):
            database.get_students(faculty_id=self.student_user_id)
        with self.assertRaises(PermissionError):
            database.get_all_academic_records(faculty_id=self.student_user_id)
        with self.assertRaises(PermissionError):
            database.get_classroom_activity_stats(faculty_id=self.student_user_id)
        with self.assertRaises(PermissionError):
            database.get_lab_exam_catalog(faculty_id=self.student_user_id)

    def test_signed_qr_records_only_the_matching_student(self):
        qr = QRAttendanceSystem()
        token = qr.generate_token(
            self.subject_id, date.today().isoformat(), faculty_id=self.faculty_user_id,
            section="A", class_id=self.class_id,
        )
        self.assertTrue(qr.validate_token(token)["valid"])
        qr.record_attendance(self.student_user_id, token)
        student = database.get_student_profile(self.student_user_id)
        self.assertIsNotNone(student)
        rows = database.get_attendance_session_records(
            self.subject_id, date.today().isoformat(), "A", self.class_id
        )
        self.assertEqual(rows[self.student_id][:1], ("Present",))
        with self.assertRaises(ValueError):
            qr.record_attendance(self.student_user_id, token)

    def test_assignment_attachment_is_copied_to_managed_storage(self):
        source = self.root / "submission.txt"
        source.write_text("A sample assignment submission.", encoding="utf-8")
        self.assertTrue(database.submit_assignment(self.assignment_id, self.student_user_id, "Written work", str(source)))
        with self.assertRaises(PermissionError):
            database.get_assignment_submissions(self.assignment_id, faculty_id=self.student_user_id)
        row = database.get_assignment_submissions(self.assignment_id, faculty_id=self.faculty_user_id)[0]
        reference = row[4]
        self.assertTrue(reference.startswith(STORAGE_PREFIX))
        self.assertEqual(storage_service.resolve(reference).read_text(encoding="utf-8"),
                         "A sample assignment submission.")
        self.assertEqual(storage_service.file_name(reference), "submission.txt")
        forbidden = self.root / "submission.exe"
        forbidden.write_text("not executable content", encoding="utf-8")
        with self.assertRaises(ValueError):
            database.submit_assignment(
                self.assignment_id, self.student_user_id, "", str(forbidden)
            )

    def test_course_document_is_stored_and_retrievable_locally(self):
        source = self.root / "course-notes.md"
        source.write_text(
            "A uniqueness-conscious cache stores entries atomically for quick reuse.",
            encoding="utf-8",
        )
        doc_id = rag_engine.ingest_file(
            "Cache Notes", str(source), subject_id=self.subject_id,
            uploaded_by=self.faculty_user_id, unit_number=1, class_id=self.class_id,
        )
        self.assertGreater(doc_id, 0)
        row = next(note for note in database.get_notes() if note[4] == "Cache Notes")
        self.assertTrue(row[5].startswith(STORAGE_PREFIX))
        self.assertIn("atomically", rag_engine.query("How does a uniqueness-conscious cache store entries?")["answer"])
        with self.assertRaises(PermissionError):
            rag_engine.ingest_file(
                "Student Upload", str(source), subject_id=self.subject_id,
                uploaded_by=self.student_user_id,
            )

    def test_rag_answers_from_class_material_for_faculty_and_enrolled_students(self):
        faculty_id = database.authenticate_user("faculty1", "Faculty123!")[0]
        student_user_id = database.authenticate_user("student3", "Student123!")[0]
        other_student_id = database.authenticate_user("student1", "Student123!")[0]
        connection = database.get_connection()
        try:
            class_id = connection.execute(
                "SELECT class_id FROM students WHERE user_id = ?", (student_user_id,)
            ).fetchone()[0]
            subject_id = connection.execute(
                "SELECT id FROM subjects WHERE code = 'CS301'"
            ).fetchone()[0]
        finally:
            connection.close()

        rag_engine.ingest_text_document(
            "Class Scoped Graph Notes",
            "Zytherium graph traversal records amber vertices with a lantern index for the final route.",
            subject_id, file_path="class-scoped-rag-test", uploaded_by=faculty_id,
            class_id=class_id,
        )
        question = "How does zytherium graph traversal record amber vertices?"
        faculty_answer = rag_engine.query(question, role="faculty", user_id=faculty_id)
        student_answer = rag_engine.query(question, role="student", user_id=student_user_id)
        outside_answer = rag_engine.query(question, role="student", user_id=other_student_id)
        self.assertIn("Zytherium", faculty_answer["answer"])
        self.assertIn("Zytherium", student_answer["answer"])
        self.assertEqual(faculty_answer["citations"][0]["source"], student_answer["citations"][0]["source"])
        self.assertFalse(outside_answer["citations"])

    def test_rag_recovers_clear_spelling_slips_from_indexed_material(self):
        faculty_id = database.authenticate_user("faculty1", "Faculty123!")[0]
        student_user_id = database.authenticate_user("student3", "Student123!")[0]
        connection = database.get_connection()
        try:
            class_id = connection.execute(
                "SELECT class_id FROM students WHERE user_id = ?", (student_user_id,)
            ).fetchone()[0]
            subject_id = connection.execute(
                "SELECT id FROM subjects WHERE code = 'CS301'"
            ).fetchone()[0]
        finally:
            connection.close()
        rag_engine.ingest_text_document(
            "Hash Table Collision Notes",
            "Collision resolution uses separate chaining to store multiple keys in one hash bucket.",
            subject_id, file_path="rag-typo-test", uploaded_by=faculty_id, class_id=class_id,
        )
        result = rag_engine.query(
            "How does colision resolution store multiple keys?",
            role="student", user_id=student_user_id,
        )
        self.assertIn("separate chaining", result["answer"])
        self.assertTrue(result["citations"])

    def test_voice_normalizes_common_vscode_and_navigation_variants(self):
        self.assertEqual(_normalize_voice_text("open v s c"), "open vs code")
        self.assertEqual(_normalize_voice_text("open visual studio code"), "open vs code")
        self.assertEqual(_normalize_voice_text("go to next slide"), "next slide")
        engine = VoiceEngine.__new__(VoiceEngine)
        self.assertEqual(engine.process_command("open vscod")["intent"], "launch_app")

    def test_voice_routes_file_and_app_search_to_safe_search_results(self):
        engine = VoiceEngine.__new__(VoiceEngine)
        file_search = engine.process_command("search for a file lab report")
        self.assertEqual(file_search["intent"], "search_local_item")
        self.assertEqual(file_search["query"], "lab report")
        self.assertEqual(file_search["kind"], "files")
        app_search = engine.process_command("find an app chrome")
        self.assertEqual(app_search["kind"], "apps")
        open_file = engine.process_command("open the file lab report")
        self.assertEqual(open_file["kind"], "files")

    def test_local_file_search_matches_name_and_extension(self):
        search_root = self.root / "search-folder"
        search_root.mkdir(exist_ok=True)
        match = search_root / "Lab_Report_2026.pdf"
        match.write_bytes(b"test")
        with patch("voice.local_search._file_roots", return_value=[search_root]):
            results = search_local_items("lab report pdf", "files")
        self.assertEqual(len(results), 1)
        self.assertEqual(Path(results[0]["path"]), match)

    def test_speech_audio_boosts_quiet_voice_and_suppresses_near_silence(self):
        import numpy as np

        quiet_voice = np.full(4000, 450, dtype=np.int16).tobytes()
        prepared, level, gain = _prepare_audio(quiet_voice)
        prepared_samples = np.frombuffer(prepared, dtype=np.int16)
        self.assertGreater(float(np.sqrt(np.mean(prepared_samples.astype(float) ** 2))), 450)
        self.assertGreater(level, 0)
        self.assertGreater(gain, 1.0)

        near_silence = np.full(4000, 40, dtype=np.int16).tobytes()
        prepared_silence, silence_level, _ = _prepare_audio(near_silence)
        self.assertEqual(set(np.frombuffer(prepared_silence, dtype=np.int16)), {0})
        self.assertEqual(silence_level, 0)

    def test_attendance_pdf_uses_readable_landscape_page(self):
        from pypdf import PdfReader

        output = self.root / "attendance-readable.pdf"
        self.assertTrue(report_generator.export_attendance_pdf_report(
            str(output), class_id=self.class_id,
        ))
        page = PdfReader(str(output)).pages[0]
        self.assertGreater(float(page.mediabox.width), float(page.mediabox.height))
        self.assertTrue(page.extract_text().strip())

    def test_lab_manuals_and_experiment_progress_work_for_both_roles(self):
        faculty_id = database.authenticate_user("faculty1", "Faculty123!")[0]
        student_user_id = database.authenticate_user("student3", "Student123!")[0]
        other_student_id = database.authenticate_user("student1", "Student123!")[0]
        connection = database.get_connection()
        try:
            class_id = connection.execute(
                "SELECT class_id FROM students WHERE user_id = ?", (student_user_id,)
            ).fetchone()[0]
            subject_id = connection.execute(
                "SELECT id FROM subjects WHERE code = 'CS301'"
            ).fetchone()[0]
        finally:
            connection.close()
        manual = self.root / "lab-manual.md"
        manual.write_text("Steps for the class lab exercise.", encoding="utf-8")
        experiment_id = database.create_lab_experiment(
            faculty_id, class_id, subject_id, 99, "Class-scoped graph lab",
            "Implement the graph walk and describe your output.", str(manual),
        )

        self.assertTrue(any(row[0] == experiment_id
                            for row in database.get_lab_experiments(faculty_id=faculty_id)))
        student_labs = database.get_lab_experiments(student_user_id=student_user_id)
        self.assertTrue(any(row[0] == experiment_id for row in student_labs))
        self.assertFalse(any(row[0] == experiment_id
                             for row in database.get_lab_experiments(student_user_id=other_student_id)))
        manual_reference = next(row[6] for row in student_labs if row[0] == experiment_id)
        self.assertTrue(storage_service.resolve(manual_reference).is_file())
        self.assertEqual(database.get_student_lab_progress(student_user_id)[0][6], "Not started")

        database.submit_lab_experiment(
            experiment_id, student_user_id,
            "I completed the graph traversal using a visited set and queue.",
        )
        progress = database.get_lab_experiment_progress(experiment_id, faculty_id)
        self.assertEqual(progress[0][3], "Submitted for Review")
        self.assertIn("visited set", progress[0][4])
        database.review_lab_submission(progress[0][6], faculty_id, "Needs Revision")
        self.assertEqual(database.get_student_lab_progress(student_user_id)[0][6], "Needs Revision")
        database.submit_lab_experiment(
            experiment_id, student_user_id,
            "I revised the graph traversal and documented the visited set and result.",
        )
        progress = database.get_lab_experiment_progress(experiment_id, faculty_id)
        database.review_lab_submission(progress[0][6], faculty_id, "Completed")
        self.assertEqual(database.get_student_lab_progress(student_user_id)[0][6], "Completed")
        self.assertEqual(storage_service.remove_orphaned_files(), 0)

    def test_startup_cleanup_removes_unreferenced_uploads(self):
        source = self.root / "orphan.txt"
        source.write_text("Temporary upload with no related record.", encoding="utf-8")
        reference = storage_service.store_file(
            source, uploaded_by=self.student_user_id, category="test_uploads", allowed_extensions={".txt"}
        )
        self.assertTrue(storage_service.resolve(reference).exists())
        self.assertGreaterEqual(storage_service.remove_orphaned_files(), 1)
        self.assertFalse(storage_service.resolve(reference).exists())

    def test_legacy_database_is_copied_without_losing_existing_tables(self):
        source = sqlite3.connect(database.LEGACY_DB_PATH)
        source.execute("CREATE TABLE migration_check (value TEXT NOT NULL)")
        source.execute("INSERT INTO migration_check VALUES ('preserved')")
        source.commit()
        source.close()
        target = self.root / "migrated.sqlite3"
        previous_path = database.DB_PATH
        database.DB_PATH = target
        try:
            connection = database.get_connection()
            try:
                value = connection.execute("SELECT value FROM migration_check").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(value, "preserved")
        finally:
            database.DB_PATH = previous_path


if __name__ == "__main__":
    unittest.main()
