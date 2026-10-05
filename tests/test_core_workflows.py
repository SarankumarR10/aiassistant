"""Dependency-light tests for EduPilot's core local workflows."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import database.database as database
from ai.rag_engine import rag_engine
from attendance.qr_attendance import QRAttendanceSystem
from storage.local_storage import STORAGE_PREFIX, storage_service


class CoreWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="edupilot-tests-")
        cls.root = Path(cls.temp.name)
        database.DB_PATH = cls.root / "test.sqlite3"
        database.LEGACY_DB_PATH = cls.root / "legacy.sqlite3"
        storage_service.root = cls.root / "uploads"
        database.initialize_database()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_database_initialization_is_idempotent_and_passwords_are_hashed(self):
        database.initialize_database()
        self.assertEqual(database.authenticate_user("faculty", "faculty123")[2], "faculty")
        self.assertIsNone(database.authenticate_user("faculty", "wrong-password"))
        connection = database.get_connection()
        try:
            password = connection.execute(
                "SELECT password FROM users WHERE username = 'faculty'"
            ).fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            connection.close()
        self.assertTrue(password.startswith("pbkdf2_sha256$"))
        self.assertEqual(version, 2)
        with self.assertRaises(PermissionError):
            database.get_students(faculty_id=2)
        with self.assertRaises(PermissionError):
            database.get_all_academic_records(faculty_id=2)
        with self.assertRaises(PermissionError):
            database.get_classroom_activity_stats(faculty_id=2)
        with self.assertRaises(PermissionError):
            database.get_lab_exam_catalog(faculty_id=2)

    def test_signed_qr_records_only_the_matching_student(self):
        qr = QRAttendanceSystem()
        token = qr.generate_token(1, date.today().isoformat(), faculty_id=1, section="C")
        self.assertTrue(qr.validate_token(token)["valid"])
        qr.record_attendance(2, token)
        student = database.get_student_profile(2)
        self.assertIsNotNone(student)
        rows = database.get_attendance_session_records(1, date.today().isoformat(), "C")
        self.assertEqual(rows[student[0]][:1], ("Present",))
        with self.assertRaises(ValueError):
            qr.record_attendance(2, token)

    def test_assignment_attachment_is_copied_to_managed_storage(self):
        source = self.root / "submission.txt"
        source.write_text("A sample assignment submission.", encoding="utf-8")
        self.assertTrue(database.submit_assignment(1, 2, "Written work", str(source)))
        with self.assertRaises(PermissionError):
            database.get_assignment_submissions(1, faculty_id=2)
        row = database.get_assignment_submissions(1, faculty_id=1)[0]
        reference = row[4]
        self.assertTrue(reference.startswith(STORAGE_PREFIX))
        self.assertEqual(storage_service.resolve(reference).read_text(encoding="utf-8"),
                         "A sample assignment submission.")
        self.assertEqual(storage_service.file_name(reference), "submission.txt")
        forbidden = self.root / "submission.exe"
        forbidden.write_text("not executable content", encoding="utf-8")
        with self.assertRaises(ValueError):
            database.submit_assignment(1, 2, "", str(forbidden))

    def test_course_document_is_stored_and_retrievable_locally(self):
        source = self.root / "course-notes.md"
        source.write_text(
            "A uniqueness-conscious cache stores entries atomically for quick reuse.",
            encoding="utf-8",
        )
        doc_id = rag_engine.ingest_file(
            "Cache Notes", str(source), subject_id=1, uploaded_by=1, unit_number=1
        )
        self.assertGreater(doc_id, 0)
        row = next(note for note in database.get_notes() if note[4] == "Cache Notes")
        self.assertTrue(row[5].startswith(STORAGE_PREFIX))
        self.assertIn("atomically", rag_engine.query("How does a uniqueness-conscious cache store entries?")["answer"])
        with self.assertRaises(PermissionError):
            rag_engine.ingest_file("Student Upload", str(source), subject_id=1, uploaded_by=2)

    def test_startup_cleanup_removes_unreferenced_uploads(self):
        source = self.root / "orphan.txt"
        source.write_text("Temporary upload with no related record.", encoding="utf-8")
        reference = storage_service.store_file(
            source, uploaded_by=2, category="test_uploads", allowed_extensions={".txt"}
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
