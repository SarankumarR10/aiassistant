import sqlite3
import hashlib
import hmac
import os
import secrets
import sys
import base64
import json
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


def get_app_data_dir() -> Path:
    """Return a writable per-user data directory on Windows, macOS, and Linux."""
    configured = os.environ.get("EDUPILOT_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "EduPilot"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "EduPilot"
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "edupilot"


APP_DATA_DIR = get_app_data_dir()
LEGACY_DB_PATH = BASE_DIR / "edupilot.db"
DB_PATH = Path(os.environ.get("EDUPILOT_DB_PATH", APP_DATA_DIR / "edupilot.db")).expanduser()
_POSTGRES_URL_FILE = APP_DATA_DIR / "postgres_url.txt"
POSTGRES_URL = os.environ.get("EDUPILOT_DATABASE_URL", "").strip()
if not POSTGRES_URL and _POSTGRES_URL_FILE.is_file():
    POSTGRES_URL = _POSTGRES_URL_FILE.read_text(encoding="utf-8").strip()
_PASSWORD_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PASSWORD_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${_PASSWORD_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, stored: str) -> tuple[bool, bool]:
    """Return (valid, needs_upgrade); recognize legacy plaintext demo credentials."""
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = stored.split("$", 3)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
            ).hex()
            return hmac.compare_digest(actual, expected), False
        except (ValueError, TypeError):
            return False, False
    return hmac.compare_digest(password, stored), True


def _audit(cursor, user_id: int | None, action: str, details: str = "") -> None:
    cursor.execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, details[:500]),
    )


def get_connection():
    if POSTGRES_URL:
        try:
            import psycopg
            from database.postgres_compat import PostgresConnection
        except ImportError as error:
            raise RuntimeError(
                "PostgreSQL is configured but its driver is missing. Install the project requirements."
            ) from error
        try:
            return PostgresConnection(psycopg.connect(POSTGRES_URL))
        except Exception as error:
            raise RuntimeError(
                "Could not connect to PostgreSQL. Check EDUPILOT_DATABASE_URL, that the server is running, "
                "and that the database/user exist."
            ) from error

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if (not os.environ.get("EDUPILOT_DB_PATH")
            and DB_PATH.resolve() != LEGACY_DB_PATH.resolve()
            and not DB_PATH.exists() and LEGACY_DB_PATH.is_file()):
        old_database = sqlite3.connect(LEGACY_DB_PATH)
        new_database = sqlite3.connect(DB_PATH)
        try:
            old_database.backup(new_database)
        finally:
            old_database.close()
            new_database.close()
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def get_local_connection():
    """Open the per-device SQLite store for private, device-local features."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_local_database() -> None:
    """Create local-only tables without putting private data in shared PostgreSQL."""
    with closing(get_local_connection()) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS local_settings (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS voice_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_voice_notes_owner_updated
                ON voice_notes(user_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS face_enrollments (
                student_id INTEGER PRIMARY KEY,
                encrypted_samples TEXT NOT NULL,
                consented_by INTEGER NOT NULL,
                consented_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)
        connection.commit()


def _clear_local_demo_data_once(version: str) -> None:
    """Clear private device records once after the shared academic reset."""
    with closing(get_local_connection()) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS local_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = connection.execute("SELECT value FROM local_settings WHERE name='application_data_reset_version'").fetchone()
        if row and row[0] == version:
            return
        connection.execute("DELETE FROM voice_notes")
        connection.execute("DELETE FROM face_enrollments")
        connection.execute("DELETE FROM local_settings")
        connection.execute("INSERT INTO local_settings(name,value) VALUES('application_data_reset_version',?)", (version,))
        connection.commit()
    try:
        import keyring
        keyring.delete_password("EduPilot", "face_encryption_key")
    except Exception:
        pass


def purge_face_enrollments() -> int:
    """Remove expired templates and templates whose student account was deleted."""
    shared = get_connection()
    try:
        live_ids = [row[0] for row in shared.execute("SELECT id FROM students").fetchall()]
    finally:
        shared.close()
    cutoff = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(get_local_connection()) as local:
        if live_ids:
            marks = ",".join("?" for _ in live_ids)
            cursor = local.execute(
                f"DELETE FROM face_enrollments WHERE expires_at <= ? OR student_id NOT IN ({marks})",
                (cutoff, *live_ids),
            )
        else:
            cursor = local.execute("DELETE FROM face_enrollments")
        local.commit()
        return cursor.rowcount


def _ensure_column(cursor, table: str, column: str, declaration: str) -> None:
    """Apply an additive SQLite schema migration only when the column is missing."""
    if POSTGRES_URL:
        present = {
            row[0] for row in cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = ?",
                (table,),
            ).fetchall()
        }
    else:
        present = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
    if column not in present:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def current_academic_year() -> str:
    """Return the conventional July-to-June academic year label."""
    today = date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return f"{start}-{start + 1}"


def _get_or_create_academic_class(cursor, department: str, year: int, section: str,
                                  academic_year: str | None = None) -> int:
    department = str(department or "General").strip() or "General"
    section = str(section or "A").strip() or "A"
    year = int(year)
    academic_year = str(academic_year or current_academic_year()).strip()
    cursor.execute("""INSERT OR IGNORE INTO academic_classes
        (department, year_of_study, section, academic_year) VALUES (?, ?, ?, ?)""",
        (department, year, section, academic_year))
    return int(cursor.execute("""SELECT id FROM academic_classes WHERE department = ?
        AND year_of_study = ? AND section = ? AND academic_year = ?""",
        (department, year, section, academic_year)).fetchone()[0])


def _remove_seed_student(cursor, username: str) -> None:
    """Remove a retired built-in demo student and its dependent records."""
    user = cursor.execute("SELECT id FROM users WHERE username = ? AND role = 'student'", (username,)).fetchone()
    if not user:
        return
    user_id = int(user[0])
    student = cursor.execute("SELECT id FROM students WHERE user_id = ?", (user_id,)).fetchone()
    if student:
        student_id = int(student[0])
        for table in ("attendance_records", "academics", "assignment_submissions",
                      "lab_submissions", "lab_exam_submissions", "online_exam_attempts"):
            cursor.execute(f"DELETE FROM {table} WHERE student_id = ?", (student_id,))
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
    cursor.execute("DELETE FROM assistant_query_events WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))


def _reset_shared_application_data_once(cursor) -> bool:
    """Replace existing academic records once with the approved demo cohort."""
    version = "1"
    marker = cursor.execute("SELECT value FROM app_settings WHERE name='application_data_reset_version'").fetchone()
    if marker and marker[0] == version:
        return False

    # Delete children before parents so SQLite and PostgreSQL enforce the same
    # reset. The subject and curated FAQ catalogs remain as app reference data.
    tables = (
        "online_exam_results", "online_exam_faculty_actions", "online_exam_violations",
        "online_code_submissions", "online_attempt_questions", "online_student_answers",
        "online_exam_attempts", "online_exam_questions", "online_question_options",
        "online_coding_test_cases", "online_questions", "online_exams",
        "lab_exam_submissions", "lab_submissions", "assignment_submissions",
        "attendance_records", "academics", "document_chunks", "reminders",
        "assistant_query_events", "audit_log", "announcements",
        "assignments", "notes", "documents", "question_banks", "lab_experiments",
        "lab_exams", "timetables", "attendance_sessions", "teaching_assignments",
        "faculty_profiles", "students", "academic_classes", "users",
    )
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
    cursor.execute("DELETE FROM subjects")
    cursor.execute("DELETE FROM app_settings WHERE name='academic_demo_seed_version'")
    cursor.execute("INSERT OR REPLACE INTO app_settings(name,value) VALUES('application_data_reset_version',?)",
                   (version,))
    return True


def _seed_academic_demo_data(cursor) -> None:
    """Replace the built-in sample cohort once with class-scoped demo users."""
    version = "1"
    row = cursor.execute("SELECT value FROM app_settings WHERE name = 'academic_demo_seed_version'").fetchone()
    if row and row[0] == version:
        return

    # Keep historical rows attached to the original faculty ID.
    legacy_faculty = cursor.execute("SELECT id FROM users WHERE username='faculty' AND role='faculty'").fetchone()
    numbered_faculty = cursor.execute("SELECT id FROM users WHERE username='faculty1'").fetchone()
    if legacy_faculty and not numbered_faculty:
        cursor.execute("UPDATE users SET username='faculty1' WHERE id=?", (legacy_faculty[0],))
    for old_name in ("student4", "student5"):
        _remove_seed_student(cursor, old_name)

    faculty_seed = (
        ("faculty1", "Dr. Meera Raman", "FAC-CSE-001", "Computer Science", "Assistant Professor"),
        ("faculty2", "Prof. Arjun Menon", "FAC-CSE-002", "Computer Science", "Associate Professor"),
        ("faculty3", "Dr. Priya Nair", "FAC-CSE-003", "Computer Science", "Assistant Professor"),
    )
    faculty_ids = {}
    for username, name, employee_code, department, designation in faculty_seed:
        found = cursor.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if found:
            faculty_id = int(found[0])
            cursor.execute("UPDATE users SET password=?, role='faculty', name=? WHERE id=?",
                           (hash_password("Faculty123!"), name, faculty_id))
        else:
            cursor.execute("INSERT INTO users(username,password,role,name) VALUES(?,?,?,?)",
                           (username, hash_password("Faculty123!"), "faculty", name))
            faculty_id = int(cursor.lastrowid)
        faculty_ids[username] = faculty_id
        cursor.execute("""INSERT INTO faculty_profiles(user_id,employee_code,department,designation)
            VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET employee_code=excluded.employee_code,
            department=excluded.department, designation=excluded.designation""",
            (faculty_id, employee_code, department, designation))

    # Convert the original student login to student1 while retaining its row.
    old_student = cursor.execute("SELECT id FROM users WHERE username='student' AND role='student'").fetchone()
    numbered_student = cursor.execute("SELECT id FROM users WHERE username='student1'").fetchone()
    if old_student and not numbered_student:
        cursor.execute("UPDATE users SET username='student1' WHERE id=?", (old_student[0],))

    academic_year = current_academic_year()
    class_one = _get_or_create_academic_class(cursor, "CSE", 1, "A", academic_year)
    class_two = _get_or_create_academic_class(cursor, "CSE", 2, "A", academic_year)
    cursor.execute("UPDATE academic_classes SET created_by=? WHERE id=?", (faculty_ids["faculty1"], class_one))
    cursor.execute("UPDATE academic_classes SET created_by=? WHERE id=?", (faculty_ids["faculty1"], class_two))

    student_seed = (
        ("student1", "Asha Kumar", "26CSE001", 1, class_one),
        ("student2", "Kavin Raj", "26CSE002", 1, class_one),
        ("student3", "Nila Devi", "25CSE001", 2, class_two),
    )
    for username, name, roll_number, year, class_id in student_seed:
        found = cursor.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if found:
            user_id = int(found[0])
            cursor.execute("UPDATE users SET password=?, role='student', name=? WHERE id=?",
                           (hash_password("Student123!"), name, user_id))
        else:
            cursor.execute("INSERT INTO users(username,password,role,name) VALUES(?,?,?,?)",
                           (username, hash_password("Student123!"), "student", name))
            user_id = int(cursor.lastrowid)
        student = cursor.execute("SELECT id FROM students WHERE user_id=?", (user_id,)).fetchone()
        if student:
            cursor.execute("""UPDATE students SET roll_number=?,name=?,department='CSE',year=?,
                section='A',class_id=? WHERE id=?""",
                (roll_number, name, year, class_id, student[0]))
        else:
            cursor.execute("""INSERT INTO students(user_id,roll_number,name,department,year,section,class_id)
                VALUES(?,?,?,'CSE',?,'A',?)""", (user_id, roll_number, name, year, class_id))

    for code, name in (("CS301", "Data Structures"), ("CS302", "Database Management Systems"),
                       ("CS303", "Computer Networks"), ("CS304", "Python Programming")):
        cursor.execute("INSERT OR IGNORE INTO subjects(code,name) VALUES(?,?)", (code, name))
    subject_ids = {record[1]: int(record[0]) for record in cursor.execute("SELECT id,code FROM subjects").fetchall()}
    allocations = (
        (class_one, "CS303", "faculty2"), (class_one, "CS304", "faculty3"),
        (class_two, "CS301", "faculty1"), (class_two, "CS302", "faculty2"),
    )
    for class_id, code, faculty_name in allocations:
        subject_id = subject_ids.get(code)
        if subject_id is not None:
            cursor.execute("""INSERT INTO teaching_assignments(class_id,subject_id,faculty_id,academic_term)
                VALUES(?,?,?,'Full Year') ON CONFLICT(class_id,subject_id,academic_term)
                DO UPDATE SET faculty_id=excluded.faculty_id""",
                (class_id, subject_id, faculty_ids[faculty_name]))

    # Link legacy course data only when the current allocation identifies one class.
    for table in ("assignments", "notes", "documents", "question_banks", "lab_experiments",
                  "lab_exams", "online_exams"):
        rows = cursor.execute(f"SELECT id,subject_id FROM {table} WHERE class_id IS NULL").fetchall()
        for record_id, subject_id in rows:
            offered = cursor.execute("SELECT DISTINCT class_id FROM teaching_assignments WHERE subject_id=?",
                                     (subject_id,)).fetchall()
            if len(offered) == 1:
                cursor.execute(f"UPDATE {table} SET class_id=? WHERE id=?", (offered[0][0], record_id))
    cursor.execute("""UPDATE assignments SET faculty_id=(SELECT ta.faculty_id FROM teaching_assignments ta
        WHERE ta.class_id=assignments.class_id AND ta.subject_id=assignments.subject_id LIMIT 1)
        WHERE faculty_id IS NULL AND class_id IS NOT NULL""")
    for record_id, subject_id in cursor.execute("SELECT id,subject_id FROM timetables WHERE class_id IS NULL").fetchall():
        offered = cursor.execute("SELECT class_id,faculty_id FROM teaching_assignments WHERE subject_id=?",
                                 (subject_id,)).fetchall()
        if len({record[0] for record in offered}) == 1:
            cursor.execute("UPDATE timetables SET class_id=?,faculty_id=? WHERE id=?",
                           (offered[0][0], offered[0][1], record_id))

    cursor.execute("INSERT OR REPLACE INTO app_settings(name,value) VALUES('academic_demo_seed_version',?)", (version,))


def get_or_create_app_secret(name: str) -> str:
    """Read or create a secret in the store whose scope matches its use.

    Device-only installs keep secrets in local SQLite. When PostgreSQL is
    configured, shared features such as QR attendance need one common key so
    tokens issued on one connected device can be validated by another.
    """
    if POSTGRES_URL:
        conn = get_connection()
        try:
            row = conn.execute("SELECT value FROM app_settings WHERE name = ?", (name,)).fetchone()
            if row:
                return row[0]
            value = secrets.token_hex(32)
            # INSERT OR IGNORE maps to ON CONFLICT DO NOTHING for PostgreSQL.
            # The follow-up read also handles two clients creating the same
            # setting concurrently without replacing the winner's secret.
            conn.execute("INSERT OR IGNORE INTO app_settings (name, value) VALUES (?, ?)", (name, value))
            conn.commit()
            row = conn.execute("SELECT value FROM app_settings WHERE name = ?", (name,)).fetchone()
            if not row:
                raise RuntimeError("Could not create the shared application secret.")
            return row[0]
        finally:
            conn.close()

    conn = get_local_connection()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS local_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = conn.execute("SELECT value FROM local_settings WHERE name = ?", (name,)).fetchone()
        if row:
            return row[0]
        value = secrets.token_hex(32)
        conn.execute("INSERT OR IGNORE INTO local_settings (name, value) VALUES (?, ?)", (name, value))
        conn.commit()
        row = conn.execute("SELECT value FROM local_settings WHERE name = ?", (name,)).fetchone()
        if not row:
            raise RuntimeError("Could not create the local application secret.")
        return row[0]
    finally:
        conn.close()


def _local_face_cipher():
    """Return a Fernet cipher keyed by the operating system credential vault."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as error:
        raise RuntimeError(
            "Encrypted face enrollment needs cryptography. Install the optional project requirements and restart EduPilot."
        ) from error
    try:
        import keyring
    except ImportError as error:
        raise RuntimeError(
            "Face enrollment needs the optional keyring package to protect its encryption key in the OS credential vault."
        ) from error

    service, username = "EduPilot", "face_encryption_key"
    try:
        backend = keyring.get_keyring()
        if getattr(backend, "priority", 0) <= 0:
            raise RuntimeError("No secure OS credential vault is available on this device.")
        value = keyring.get_password(service, username)
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(f"Could not access the OS credential vault: {error}") from error

    conn = get_local_connection()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS local_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        legacy = conn.execute("SELECT value FROM local_settings WHERE name = ?", (username,)).fetchone()
        if not value:
            value = legacy[0] if legacy else base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
            try:
                keyring.set_password(service, username, value)
                if keyring.get_password(service, username) != value:
                    raise RuntimeError("The OS credential vault did not retain the face encryption key.")
            except RuntimeError:
                raise
            except Exception as error:
                raise RuntimeError(f"Could not save the face encryption key in the OS credential vault: {error}") from error
        conn.execute("DELETE FROM local_settings WHERE name = ?", (username,))
        conn.commit()
        try:
            return Fernet(value.encode("ascii"))
        except (ValueError, TypeError) as error:
            raise RuntimeError("The face encryption key in the OS credential vault is invalid.") from error
    finally:
        conn.close()


def save_student_face_enrollment(student_id: int, samples: list[str], faculty_id: int,
                                 consent_confirmed: bool) -> str:
    """Store encrypted face crops locally for 90 days after explicit opt-in confirmation."""
    if not consent_confirmed:
        raise PermissionError("Confirm that this student has opted in before saving face enrollment.")
    if not samples or len(samples) < 5 or len(samples) > 20:
        raise ValueError("Capture between 5 and 20 clear face samples.")
    if any(not isinstance(sample, str) or len(sample) > 200_000 for sample in samples):
        raise ValueError("A face sample is invalid or too large.")

    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        student = conn.execute("SELECT 1 FROM students WHERE id = ?", (student_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can enroll a student face.")
        if not student:
            raise ValueError("The selected student no longer exists.")
    finally:
        conn.close()

    cipher = _local_face_cipher()
    now = datetime.now(timezone.utc)
    consented_at = now.isoformat(timespec="seconds")
    expires_at = (now + timedelta(days=90)).isoformat(timespec="seconds")
    encrypted = cipher.encrypt(json.dumps(samples, separators=(",", ":")).encode("utf-8")).decode("ascii")
    with closing(get_local_connection()) as local:
        local.execute("""
            INSERT INTO face_enrollments(student_id, encrypted_samples, consented_by, consented_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET encrypted_samples = excluded.encrypted_samples,
                consented_by = excluded.consented_by, consented_at = excluded.consented_at,
                expires_at = excluded.expires_at
        """, (student_id, encrypted, faculty_id, consented_at, expires_at))
        local.commit()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        _audit(cursor, faculty_id, "attendance.face_enrolled", f"student={student_id}; expires={expires_at[:10]}")
        conn.commit()
    finally:
        conn.close()
    return expires_at


def get_student_face_enrollments(section: str, faculty_id: int,
                                class_id: int | None = None) -> list[tuple[int, list[str]]]:
    """Load active face samples only for a faculty-authorized section on this device."""
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can use face attendance.")
        if class_id is not None:
            student_ids = [row[0] for row in conn.execute("SELECT id FROM students WHERE class_id = ?", (class_id,)).fetchall()]
        else:
            student_ids = [row[0] for row in conn.execute("SELECT id FROM students WHERE section = ?", (section,)).fetchall()]
    finally:
        conn.close()
    if not student_ids:
        return []

    placeholders = ",".join("?" for _ in student_ids)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(get_local_connection()) as local:
        rows = local.execute(
            f"SELECT student_id, encrypted_samples FROM face_enrollments "
            f"WHERE expires_at > ? AND student_id IN ({placeholders})",
            (now, *student_ids),
        ).fetchall()
    if not rows:
        return []
    cipher = _local_face_cipher()
    return [
        (student_id, json.loads(cipher.decrypt(encrypted.encode("ascii")).decode("utf-8")))
        for student_id, encrypted in rows
    ]


def get_student_face_enrollment_status(section: str, faculty_id: int,
                                       class_id: int | None = None) -> dict[int, str]:
    """Return active enrollment expiry dates without exposing face samples."""
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can view face enrollment status.")
        if class_id is not None:
            student_ids = [row[0] for row in conn.execute("SELECT id FROM students WHERE class_id = ?", (class_id,)).fetchall()]
        else:
            student_ids = [row[0] for row in conn.execute("SELECT id FROM students WHERE section = ?", (section,)).fetchall()]
    finally:
        conn.close()
    if not student_ids:
        return {}
    placeholders = ",".join("?" for _ in student_ids)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(get_local_connection()) as local:
        rows = local.execute(
            f"SELECT student_id, expires_at FROM face_enrollments "
            f"WHERE expires_at > ? AND student_id IN ({placeholders})",
            (now, *student_ids),
        ).fetchall()
    return {student_id: expires_at for student_id, expires_at in rows}


def delete_student_face_enrollment(student_id: int, faculty_id: int) -> bool:
    """Delete the selected student's device-local biometric samples and audit the action."""
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can delete face enrollment.")
    finally:
        conn.close()
    with closing(get_local_connection()) as local:
        cursor = local.execute("DELETE FROM face_enrollments WHERE student_id = ?", (student_id,))
        local.commit()
        deleted = cursor.rowcount > 0
    if deleted:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            _audit(cursor, faculty_id, "attendance.face_enrollment_deleted", f"student={student_id}")
            conn.commit()
        finally:
            conn.close()
    return deleted


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('faculty', 'student')),
            name TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # --------------------------------------------------------
    # STUDENTS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            roll_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            year INTEGER NOT NULL,
            section TEXT DEFAULT 'C',

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # SUBJECTS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # ATTENDANCE SESSIONS
    #
    # One row = one class conducted on one date.
    #
    # Example:
    #
    # CS301 | 2026-08-08 | Faculty | CSE-C
    #
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            subject_id INTEGER NOT NULL,
            faculty_id INTEGER NOT NULL,

            class_date TEXT NOT NULL,
            section TEXT NOT NULL DEFAULT 'C',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(subject_id, class_date, section),

            FOREIGN KEY(subject_id)
                REFERENCES subjects(id),

            FOREIGN KEY(faculty_id)
                REFERENCES users(id)
        )
    """)

    # --------------------------------------------------------
    # ATTENDANCE RECORDS
    #
    # One row = one student's attendance for one session.
    #
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,

            status TEXT NOT NULL
                CHECK(status IN ('Present', 'Absent')),

            marked_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(session_id, student_id),

            FOREIGN KEY(session_id)
                REFERENCES attendance_sessions(id)
                ON DELETE CASCADE,

            FOREIGN KEY(student_id)
                REFERENCES students(id)
                ON DELETE CASCADE
        )
    """)

    _ensure_column(cursor, "attendance_records", "verification_method", "TEXT NOT NULL DEFAULT 'manual'")

    # --------------------------------------------------------
    # ACADEMICS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS academics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,

            internal_mark REAL DEFAULT 0,
            assignment_mark REAL DEFAULT 0,
            lab_mark REAL DEFAULT 0,
            total_mark REAL DEFAULT 0,

            FOREIGN KEY(student_id)
                REFERENCES students(id),

            FOREIGN KEY(subject_id)
                REFERENCES subjects(id),

            UNIQUE(student_id, subject_id)
        )
    """)

    # --------------------------------------------------------
    # SUBJECTS
    # --------------------------------------------------------

    subjects = [
        ("CS301", "Data Structures"),
        ("CS302", "Database Management Systems"),
        ("CS303", "Computer Networks"),
        ("CS304", "Python Programming")
    ]

    for code, name in subjects:

        cursor.execute("""
            INSERT OR IGNORE INTO subjects
            (
                code,
                name
            )
            VALUES (?, ?)
        """, (
            code,
            name
        ))

    # Legacy compatibility columns; face matching is intentionally not enabled.
    _ensure_column(cursor, "students", "face_encoding", "TEXT")
    _ensure_column(cursor, "students", "qr_token", "TEXT")

    # --------------------------------------------------------
    # TIMETABLE
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            room TEXT DEFAULT 'Lab 1',
            faculty_id INTEGER,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

    # --------------------------------------------------------
    # ASSIGNMENTS & SUBMISSIONS
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            max_marks INTEGER DEFAULT 100,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            submission_text TEXT,
            file_path TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            marks REAL DEFAULT 0,
            feedback TEXT,
            UNIQUE(assignment_id, student_id),
            FOREIGN KEY(assignment_id) REFERENCES assignments(id),
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)
    _ensure_column(cursor, "assignment_submissions", "graded_at", "TEXT")

    # --------------------------------------------------------
    # NOTES & QUESTION BANKS
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            unit_number INTEGER DEFAULT 1,
            uploaded_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS question_banks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            unit_number INTEGER DEFAULT 1,
            question TEXT NOT NULL,
            answer_key TEXT,
            difficulty TEXT DEFAULT 'Medium',
            marks INTEGER DEFAULT 5,
            source_kind TEXT NOT NULL DEFAULT 'Model',
            exam_year INTEGER,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)
    for column, declaration in (("source_kind", "TEXT NOT NULL DEFAULT 'Model'"), ("exam_year", "INTEGER")):
        _ensure_column(cursor, "question_banks", column, declaration)

    # --------------------------------------------------------
    # DOCUMENTS & CHUNKS (RAG)
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject_id INTEGER,
            file_path TEXT NOT NULL,
            uploaded_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            keywords TEXT,
            page_number INTEGER,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)
    _ensure_column(cursor, "document_chunks", "page_number", "INTEGER")

    # --------------------------------------------------------
    # LAB EXPERIMENTS, SUBMISSIONS & EXAMS
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            exp_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            manual_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            code_snippet TEXT,
            status TEXT DEFAULT 'Completed',
            completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(experiment_id, student_id),
            FOREIGN KEY(experiment_id) REFERENCES lab_experiments(id),
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            question_paper_text TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 60,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_exam_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            solution_code TEXT NOT NULL DEFAULT '',
            draft_code TEXT NOT NULL DEFAULT '',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at INTEGER,
            submitted_at TEXT,
            UNIQUE(exam_id, student_id),
            FOREIGN KEY(exam_id) REFERENCES lab_exams(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
    """)
    for column, declaration in (("draft_code", "TEXT NOT NULL DEFAULT ''"),
                                ("started_at", "TEXT"), ("expires_at", "INTEGER")):
        _ensure_column(cursor, "lab_exam_submissions", column, declaration)
    cursor.execute("UPDATE lab_exam_submissions SET started_at = COALESCE(started_at, submitted_at, CURRENT_TIMESTAMP)")

    # --------------------------------------------------------
    # REMINDERS & ANNOUNCEMENTS & FAQ
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            reminder_type TEXT DEFAULT 'Assignment',
            due_date TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            target_group TEXT DEFAULT 'All',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(faculty_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq_knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            keywords TEXT
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_sessions_date_subject ON attendance_sessions(class_date, subject_id, section)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_due_date ON assignments(due_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignment_submissions_assignment_date ON assignment_submissions(assignment_id, submitted_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id, chunk_index)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_page ON document_chunks(document_id, page_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_announcements_target_date ON announcements(target_group, created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reminders_owner_due ON reminders(user_id, due_date)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assistant_query_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL CHECK(category IN ('learning', 'schedule', 'exam')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assistant_query_events_created_at ON assistant_query_events(created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stored_files (
            storage_key TEXT PRIMARY KEY,
            original_name TEXT NOT NULL,
            media_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
            uploaded_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(uploaded_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stored_files_owner ON stored_files(uploaded_by, created_at DESC)")

    cursor.execute("SELECT COUNT(*) FROM faq_knowledge_base")
    if cursor.fetchone()[0] == 0:
        sample_faqs = [
            ("JVM", "What is JVM?", "Java Virtual Machine (JVM) is an abstract machine that enables your computer to run a Java program. It provides a runtime environment in which Java bytecode can be executed.", "jvm java virtual machine bytecode"),
            ("Normalization", "What is Normalization?", "Normalization is a database design technique that reduces data redundancy and eliminates undesirable characteristics like Insertion, Update, and Deletion anomalies (1NF, 2NF, 3NF, BCNF).", "normalization 1nf 2nf 3nf database dbms"),
            ("Unit 3", "Explain Unit 3 in DBMS", "Unit 3 covers Relational Database Design, Normalization, Functional Dependencies, Lossless Join Decomposition, and Multi-valued Dependencies.", "unit 3 dbms normalization functional dependency"),
            ("OS", "What is Process Synchronization?", "Process Synchronization is the task of coordinating the execution of processes in a way that no two processes can have access to the same shared data and resources simultaneously.", "os operating system process synchronization semaphore lock"),
            ("CN", "What is TCP/IP?", "TCP/IP (Transmission Control Protocol/Internet Protocol) is the conceptual model and set of communications protocols used in the Internet and similar computer networks.", "tcp ip network protocol cn computer networks")
        ]
        cursor.executemany("INSERT INTO faq_knowledge_base (category, question, answer, keywords) VALUES (?, ?, ?, ?)", sample_faqs)

    # Add concise, reviewed tutor material to both new and existing databases.
    # A version marker keeps startup idempotent and leaves faculty-authored FAQ rows untouched.
    tutor_seed_version = "2"
    seeded_version = cursor.execute(
        "SELECT value FROM app_settings WHERE name = 'tutor_faq_seed_version'"
    ).fetchone()
    if not seeded_version or seeded_version[0] != tutor_seed_version:
        tutor_faqs = [
            ("OOP", "What are the four pillars of object-oriented programming?",
             "The four commonly taught OOP principles are encapsulation (keep data and its operations together behind a controlled interface), abstraction (show the essential interface while hiding implementation detail), inheritance (derive a type from another type), and polymorphism (use one interface with behavior appropriate to the actual type).",
             "oop object oriented programming encapsulation abstraction inheritance polymorphism"),
            ("OOP", "What is encapsulation in OOP?",
             "Encapsulation groups related state and behavior in a class and controls how callers access that state. It helps protect invariants and makes implementation changes less likely to break other code.",
             "oop encapsulation class data hiding access modifiers"),
            ("OOP", "What is polymorphism in OOP?",
             "Polymorphism lets code use a shared interface while different concrete types provide their own behavior. For example, calling draw() on several Shape objects can draw each shape according to its implementation.",
             "oop polymorphism method overriding interface dynamic dispatch"),
            ("Python", "What is the difference between a Python list and tuple?",
             "A list is mutable, so its items can be added, removed, or replaced. A tuple is immutable after creation. Use a list for a changing collection and a tuple for a fixed grouping of values.",
             "python list tuple mutable immutable sequence"),
            ("Python", "How does Python handle exceptions?",
             "Put code that may fail in a try block, handle expected exception types in except blocks, use else for code that runs only when no exception occurred, and use finally for cleanup that must always run. Catch specific exceptions rather than hiding every error.",
             "python exceptions try except else finally error handling"),
            ("Java", "What is the difference between the JDK, JRE, and JVM?",
             "The JVM executes Java bytecode. The JRE is the runtime components used to run Java applications, including a JVM and libraries. The JDK adds development tools such as the compiler to the runtime components.",
             "java jdk jre jvm compiler bytecode runtime"),
            ("Java", "What is a Java interface?",
             "An interface declares a contract that implementing classes provide. It lets code depend on capabilities rather than one concrete class. Modern Java interfaces can also contain default and static methods.",
             "java interface contract implements abstraction"),
            ("DBMS", "What is the difference between a primary key and a foreign key?",
             "A primary key uniquely identifies each row in its own table and cannot be null. A foreign key refers to a key in another table, linking rows and allowing the database to enforce referential integrity.",
             "dbms database primary key foreign key relation"),
            ("DBMS", "What are the ACID properties of a database transaction?",
             "Atomicity means all transaction steps succeed or none do. Consistency preserves database rules. Isolation limits interference between concurrent transactions. Durability means committed changes survive failures.",
             "dbms database acid atomicity consistency isolation durability transaction"),
            ("SQL", "What is the difference between INNER JOIN and LEFT JOIN?",
             "INNER JOIN returns rows with matching values on both sides. LEFT JOIN returns every row from the left table and matching rows from the right; where no match exists, right-side columns are NULL.",
             "sql inner join left join tables query"),
            ("SQL", "What is a database index?",
             "An index is an auxiliary data structure that can speed up lookups and sorting on selected columns. Indexes use storage and add work to inserts, updates, and deletes, so they should target useful query patterns.",
             "sql database index performance query b-tree"),
            ("Operating Systems", "What is the difference between a process and a thread?",
             "A process is a running program with its own address space and resources. A thread is an execution path within a process; threads share that process's memory and resources, so coordination and synchronization matter.",
             "os operating system process thread concurrency memory"),
            ("Operating Systems", "What conditions are required for deadlock?",
             "The four Coffman conditions are mutual exclusion, hold and wait, no preemption, and circular wait. A deadlock requires all four conditions at once; preventing at least one can prevent deadlock.",
             "os operating system deadlock mutual exclusion hold wait preemption circular wait"),
            ("Computer Networks", "What is the difference between TCP and UDP?",
             "TCP provides an ordered, reliable byte stream with connection management and retransmission. UDP sends independent datagrams with less protocol overhead but does not guarantee delivery or ordering. The application chooses based on its needs.",
             "cn computer network tcp udp reliable datagram protocol"),
            ("Computer Networks", "What does DNS do?",
             "The Domain Name System maps names such as example.org to records used by network clients, commonly including IP addresses. Resolvers cache answers for their time-to-live to reduce repeated lookups.",
             "cn computer networks dns domain name system resolver ip address"),
            ("Data Structures", "What is the difference between a stack and a queue?",
             "A stack is last-in, first-out: the most recently added item is removed first. A queue is first-in, first-out: items are removed in arrival order. Both support efficient insertion and removal at defined ends.",
             "data structures stack queue lifo fifo"),
            ("Algorithms", "What is Big O notation?",
             "Big O describes an upper-bound growth rate for an algorithm's resource use as input size grows, commonly time or memory. It abstracts away machine-specific constants; for example, linear search is O(n) and binary search on sorted data is O(log n).",
             "algorithms big o complexity time space linear logarithmic"),
            ("Algorithms", "When can binary search be used?",
             "Binary search works when the search space is ordered and can be divided in half at each step. On a sorted array it takes O(log n) comparisons. Applying it to unsorted data without first establishing order is incorrect.",
             "algorithms binary search sorted array logarithmic complexity"),
        ]
        existing_questions = {
            row[0].strip().casefold()
            for row in cursor.execute("SELECT question FROM faq_knowledge_base").fetchall()
        }
        missing_tutor_faqs = [row for row in tutor_faqs if row[1].strip().casefold() not in existing_questions]
        cursor.executemany(
            "INSERT INTO faq_knowledge_base (category, question, answer, keywords) VALUES (?, ?, ?, ?)",
            missing_tutor_faqs,
        )
        cursor.execute(
            "INSERT OR REPLACE INTO app_settings (name, value) VALUES ('tutor_faq_seed_version', ?)",
            (tutor_seed_version,),
        )

    # Keep legacy installations with multiple seeded active exams consistent with the single-active-exam workflow.
    cursor.execute("UPDATE lab_exams SET is_active = 0 WHERE is_active = 1 AND id <> (SELECT MAX(id) FROM lab_exams WHERE is_active = 1)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lab_exams_single_active ON lab_exams(is_active) WHERE is_active = 1")

    from exams.schema import ensure_exam_schema
    ensure_exam_schema(cursor)

    # Normalized academic structure: students belong to a class, and courses
    # are assigned to both a class and a faculty member.
    cursor.execute("""CREATE TABLE IF NOT EXISTS academic_classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department TEXT NOT NULL,
        year_of_study INTEGER NOT NULL,
        section TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(department, year_of_study, section, academic_year),
        CHECK(year_of_study BETWEEN 1 AND 8)
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS faculty_profiles (
        user_id INTEGER PRIMARY KEY,
        employee_code TEXT UNIQUE,
        department TEXT NOT NULL DEFAULT '',
        designation TEXT NOT NULL DEFAULT 'Faculty',
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS teaching_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        faculty_id INTEGER NOT NULL,
        academic_term TEXT NOT NULL DEFAULT 'Full Year',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(class_id) REFERENCES academic_classes(id) ON DELETE CASCADE,
        FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
        FOREIGN KEY(faculty_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(class_id, subject_id, academic_term)
    )""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_teaching_assignments_faculty ON teaching_assignments(faculty_id, class_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_teaching_assignments_class ON teaching_assignments(class_id, subject_id)")
    _ensure_column(cursor, "students", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "attendance_sessions", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "assignments", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "assignments", "faculty_id", "INTEGER REFERENCES users(id)")
    _ensure_column(cursor, "notes", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "question_banks", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "documents", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "timetables", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "lab_experiments", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "lab_exams", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "announcements", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "online_exams", "class_id", "INTEGER REFERENCES academic_classes(id)")
    _ensure_column(cursor, "academic_classes", "created_by", "INTEGER REFERENCES users(id)")
    _ensure_column(cursor, "assistant_query_events", "user_id", "INTEGER REFERENCES users(id)")
    _ensure_column(cursor, "assistant_query_events", "class_id", "INTEGER REFERENCES academic_classes(id)")

    _reset_shared_application_data_once(cursor)

    academic_year = current_academic_year()
    legacy_classes = cursor.execute("""SELECT DISTINCT department, year, section
        FROM students WHERE class_id IS NULL ORDER BY department, year, section""").fetchall()
    for department, year, section in legacy_classes:
        department = str(department or "General").strip() or "General"
        section = str(section or "A").strip() or "A"
        cursor.execute("""INSERT OR IGNORE INTO academic_classes
            (department, year_of_study, section, academic_year) VALUES (?, ?, ?, ?)""",
            (department, int(year or 1), section, academic_year))
        class_id = cursor.execute("""SELECT id FROM academic_classes WHERE department = ?
            AND year_of_study = ? AND section = ? AND academic_year = ?""",
            (department, int(year or 1), section, academic_year)).fetchone()[0]
        cursor.execute("""UPDATE students SET class_id = ? WHERE class_id IS NULL
            AND COALESCE(department, 'General') = ? AND COALESCE(year, 1) = ?
            AND COALESCE(section, 'A') = ?""",
            (class_id, department, int(year or 1), section))
    cursor.execute("""INSERT OR IGNORE INTO faculty_profiles(user_id, department, designation)
        SELECT id, '', 'Faculty' FROM users WHERE role = 'faculty'""")
    classes = cursor.execute("SELECT id FROM academic_classes ORDER BY id").fetchall()
    faculty = cursor.execute("SELECT id FROM users WHERE role = 'faculty' ORDER BY id").fetchall()
    # Preserve the legacy demo schedule as explicit teaching assignments when
    # it can be mapped safely to a single existing class.
    if len(classes) == 1:
        class_id = classes[0][0]
        for subject_id, faculty_id in cursor.execute(
            "SELECT DISTINCT subject_id, faculty_id FROM timetables WHERE faculty_id IS NOT NULL"
        ).fetchall():
            if any(int(faculty_id) == int(item[0]) for item in faculty):
                cursor.execute("""INSERT OR IGNORE INTO teaching_assignments
                    (class_id, subject_id, faculty_id, academic_term) VALUES (?, ?, ?, 'Full Year')""",
                    (class_id, subject_id, faculty_id))

    def unique_offering(subject_id, faculty_id=None, section=None):
        sql = """SELECT DISTINCT c.id FROM teaching_assignments ta
            JOIN academic_classes c ON c.id = ta.class_id WHERE ta.subject_id = ?"""
        params = [subject_id]
        if faculty_id is not None:
            sql += " AND ta.faculty_id = ?"
            params.append(faculty_id)
        if section is not None:
            sql += " AND c.section = ?"
            params.append(section)
        found = cursor.execute(sql, tuple(params)).fetchall()
        return found[0][0] if len(found) == 1 else None

    for entry_id, subject_id, faculty_id in cursor.execute(
        "SELECT id, subject_id, faculty_id FROM timetables WHERE class_id IS NULL AND faculty_id IS NOT NULL"
    ).fetchall():
        class_id = unique_offering(subject_id, faculty_id)
        if class_id is not None:
            cursor.execute("UPDATE timetables SET class_id = ? WHERE id = ?", (class_id, entry_id))
    for table, key_column, owner_column in (("assignments", "id", "faculty_id"),
                                             ("notes", "id", "uploaded_by"),
                                             ("documents", "id", "uploaded_by"),
                                             ("online_exams", "id", "faculty_id")):
        rows = cursor.execute(f"SELECT {key_column}, subject_id, {owner_column} FROM {table} WHERE class_id IS NULL").fetchall()
        for entry_id, subject_id, owner_id in rows:
            class_id = unique_offering(subject_id, owner_id) if owner_id is not None else unique_offering(subject_id)
            if class_id is not None:
                cursor.execute(f"UPDATE {table} SET class_id = ? WHERE {key_column} = ?", (class_id, entry_id))
    for table, key_column in (("question_banks", "id"), ("lab_experiments", "id"), ("lab_exams", "id")):
        rows = cursor.execute(f"SELECT {key_column}, subject_id FROM {table} WHERE class_id IS NULL").fetchall()
        for entry_id, subject_id in rows:
            class_id = unique_offering(subject_id)
            if class_id is not None:
                cursor.execute(f"UPDATE {table} SET class_id = ? WHERE {key_column} = ?", (class_id, entry_id))
    for entry_id, subject_id, section in cursor.execute(
        "SELECT id, subject_id, section FROM attendance_sessions WHERE class_id IS NULL"
    ).fetchall():
        section = str(section or "").split("~class-", 1)[0]
        class_id = unique_offering(subject_id, section=section)
        if class_id is not None:
            cursor.execute("UPDATE attendance_sessions SET class_id = ? WHERE id = ?", (class_id, entry_id))
    cursor.execute("""UPDATE assignments SET faculty_id = (
        SELECT ta.faculty_id FROM teaching_assignments ta WHERE ta.class_id = assignments.class_id
        AND ta.subject_id = assignments.subject_id LIMIT 1)
        WHERE faculty_id IS NULL AND class_id IS NOT NULL""")

    _seed_academic_demo_data(cursor)

    cursor.execute("PRAGMA user_version = 4")
    connection.commit()
    connection.close()
    initialize_local_database()
    _clear_local_demo_data_once("1")
    purge_face_enrollments()
    from storage.local_storage import storage_service
    storage_service.remove_orphaned_files()


# ============================================================
# LOGIN
# ============================================================

def authenticate_user(username, password):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, username, role, name, password
        FROM users WHERE username = ?
    """, (username,))

    row = cursor.fetchone()
    if row is None:
        connection.close()
        return None
    valid, needs_upgrade = _verify_password(password, row[4])
    if not valid:
        connection.close()
        return None
    if needs_upgrade:
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hash_password(password), row[0]))
        connection.commit()
    user = row[:4]
    connection.close()
    return user


# ============================================================
# GET STUDENTS
# ============================================================

def get_students(section: str | None = None, *, faculty_id: int, class_id: int | None = None,
                 year: int | None = None, department: str | None = None,
                 academic_year: str | None = None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = cursor.fetchone()
    if not role or role[0] != "faculty":
        connection.close()
        raise PermissionError("Only faculty can view the student directory.")

    query = """
        SELECT
            id,
            roll_number,
            name,
            department,
            year,
            section,
            class_id
        FROM students
    """
    conditions, params = ["class_id IN (SELECT class_id FROM teaching_assignments WHERE faculty_id = ? UNION SELECT id FROM academic_classes WHERE created_by = ?)"], [faculty_id, faculty_id]
    for column, value in (("section", section), ("class_id", class_id), ("year", year),
                          ("department", department)):
        if value is not None and value != "":
            conditions.append(f"{column} = ?")
            params.append(value)
    if academic_year:
        conditions.append("class_id IN (SELECT id FROM academic_classes WHERE academic_year = ?)")
        params.append(academic_year)
    cursor.execute(query + (" WHERE " + " AND ".join(conditions) if conditions else "")
                   + " ORDER BY department, year, section, roll_number", tuple(params))

    students = cursor.fetchall()

    connection.close()

    return students


# ============================================================
# GET SUBJECTS
# ============================================================

def get_subjects(*, faculty_id: int | None = None, class_id: int | None = None,
                 student_user_id: int | None = None):

    connection = get_connection()
    cursor = connection.cursor()

    if student_user_id is not None:
        student_class = cursor.execute("SELECT class_id FROM students WHERE user_id = ?", (student_user_id,)).fetchone()
        class_id = student_class[0] if student_class else None
        if class_id is None:
            connection.close()
            return []
    if class_id is not None or faculty_id is not None:
        conditions, params = [], []
        if class_id is not None:
            conditions.append("ta.class_id = ?")
            params.append(class_id)
        if faculty_id is not None:
            conditions.append("ta.faculty_id = ?")
            params.append(faculty_id)
        cursor.execute("""SELECT DISTINCT s.id, s.code, s.name FROM subjects s
            JOIN teaching_assignments ta ON ta.subject_id = s.id WHERE """
            + " AND ".join(conditions) + " ORDER BY s.code", tuple(params))
        rows = cursor.fetchall()
        if rows or class_id is not None:
            connection.close()
            return rows
        # Compatibility for a legacy database or a newly created class before
        # the faculty has allocated its first course.
    cursor.execute("SELECT id, code, name FROM subjects ORDER BY code")

    subjects = cursor.fetchall()

    connection.close()

    return subjects


# ============================================================
# SAVE ATTENDANCE
# ============================================================

def save_attendance(
    records,
    subject_id,
    attendance_date,
    faculty_id,
    section="C",
    verification_method="manual",
    class_id: int | None = None,
):
    if not isinstance(records, dict) or not records:
        raise ValueError("Attendance cannot be saved without student records.")
    try:
        date.fromisoformat(str(attendance_date))
    except (TypeError, ValueError) as error:
        raise ValueError("Choose a valid attendance date.") from error
    section = str(section or "").strip()
    if not section:
        raise ValueError("Choose a class section.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        faculty = cursor.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not faculty or faculty[0] != "faculty":
            raise PermissionError("Only a faculty account can save attendance.")
        if not cursor.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
            raise ValueError("Choose a valid subject.")

        if class_id is not None:
            roster = {row[0] for row in cursor.execute("SELECT id FROM students WHERE class_id = ?", (class_id,)).fetchall()}
            class_row = cursor.execute("SELECT section FROM academic_classes WHERE id = ?", (class_id,)).fetchone()
            if not class_row or class_row[0] != section:
                raise ValueError("The selected class no longer matches the attendance roster.")
            session_section = f"{section}~class-{class_id}"
            if not cursor.execute("SELECT 1 FROM teaching_assignments WHERE class_id=? AND subject_id=? AND faculty_id=?",
                                  (class_id, subject_id, faculty_id)).fetchone():
                raise PermissionError("This subject is not assigned to you for the selected class.")
        else:
            roster = {row[0] for row in cursor.execute("SELECT id FROM students WHERE section = ?", (section,)).fetchall()}
            session_section = section
        submitted = {int(student_id) for student_id in records}
        if not roster:
            raise ValueError(f"There are no enrolled students in section {section}.")
        if submitted != roster:
            raise ValueError("The attendance list has changed. Reload the register and mark every enrolled student.")

        normalized_records = []
        for student_id, value in records.items():
            if isinstance(value, (tuple, list)) and len(value) == 2:
                status, method = value
            else:
                status, method = value, verification_method
            if status not in ("Present", "Absent"):
                raise ValueError(f"Mark every student Present or Absent before saving (student {student_id}).")
            if method not in ("manual", "voice", "qr", "face"):
                raise ValueError(f"Invalid attendance verification method: {method}.")
            normalized_records.append((int(student_id), status, method))

        cursor.execute("""
            INSERT OR IGNORE INTO attendance_sessions
                (subject_id, faculty_id, class_date, section, class_id)
            VALUES (?, ?, ?, ?, ?)
        """, (subject_id, faculty_id, attendance_date, session_section, class_id))
        session = cursor.execute("""
            SELECT id FROM attendance_sessions
            WHERE subject_id = ? AND class_date = ? AND section = ?
        """, (subject_id, attendance_date, session_section)).fetchone()
        if session is None:
            raise RuntimeError("Unable to open the attendance session.")
        session_id = session[0]

        for student_id, status, method in normalized_records:
            cursor.execute("""
                INSERT INTO attendance_records
                    (session_id, student_id, status, verification_method)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, student_id)
                DO UPDATE SET status = excluded.status,
                              verification_method = excluded.verification_method,
                              marked_at = CURRENT_TIMESTAMP
            """, (session_id, student_id, status, method))

        _audit(cursor, faculty_id, "attendance.saved", f"session={session_id}; students={len(records)}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_attendance_session_records(subject_id: int, attendance_date: str, section: str = "C",
                                   class_id: int | None = None) -> dict:
    conn = get_connection()
    if class_id is not None:
        rows = conn.execute("""
        SELECT ar.student_id, ar.status, ar.verification_method
        FROM attendance_records ar JOIN attendance_sessions s ON s.id = ar.session_id
        WHERE s.subject_id = ? AND s.class_date = ? AND s.class_id = ?
        """, (subject_id, attendance_date, class_id)).fetchall()
    else:
        rows = conn.execute("""
        SELECT ar.student_id, ar.status, ar.verification_method
        FROM attendance_records ar
        JOIN attendance_sessions s ON s.id = ar.session_id
        WHERE s.subject_id = ? AND s.class_date = ? AND s.section = ?
        """, (subject_id, attendance_date, section)).fetchall()
    conn.close()
    return {student_id: (status, method) for student_id, status, method in rows}


def mark_student_attendance_from_qr(user_id: int, subject_id: int, attendance_date: str,
                                   faculty_id: int, section: str,
                                   class_id: int | None = None) -> None:
    if attendance_date != date.today().isoformat():
        raise ValueError("This attendance code is not for today.")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT st.id, st.section, u.role, st.class_id
        FROM students st JOIN users u ON u.id = st.user_id
        WHERE st.user_id = ?
    """, (user_id,))
    student = cursor.fetchone()
    cursor.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    faculty = cursor.fetchone()
    cursor.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,))
    subject = cursor.fetchone()
    if not student or student[2] != "student":
        conn.close()
        raise PermissionError("A student account is required to mark QR attendance.")
    if class_id is not None and student[3] != class_id:
        conn.close()
        raise PermissionError("This attendance code is for a different academic class.")
    if class_id is None and student[1] != section:
        conn.close()
        raise PermissionError("This attendance code is for a different class section.")
    if not faculty or faculty[0] != "faculty" or not subject:
        conn.close()
        raise ValueError("The attendance code refers to an invalid class session.")
    if class_id is not None:
        assigned_class = cursor.execute("SELECT section FROM academic_classes WHERE id = ?", (class_id,)).fetchone()
        teaching = cursor.execute("""SELECT 1 FROM teaching_assignments
            WHERE class_id = ? AND subject_id = ? AND faculty_id = ?""",
            (class_id, subject_id, faculty_id)).fetchone()
        if not assigned_class or not teaching:
            conn.close()
            raise PermissionError("The QR code does not match an assigned class subject.")
        section = assigned_class[0]
    session_section = f"{section}~class-{class_id}" if class_id is not None else student[1]
    cursor.execute("""
        INSERT OR IGNORE INTO attendance_sessions (subject_id, faculty_id, class_date, section, class_id)
        VALUES (?, ?, ?, ?, ?)
    """, (subject_id, faculty_id, attendance_date, session_section, class_id))
    cursor.execute("""
        SELECT id FROM attendance_sessions
        WHERE subject_id = ? AND class_date = ? AND section = ?
    """, (subject_id, attendance_date, session_section))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise ValueError("Could not open the attendance session.")
    session_id = session[0]
    cursor.execute("""
        INSERT INTO attendance_records (session_id, student_id, status, verification_method)
        VALUES (?, ?, 'Present', 'qr')
        ON CONFLICT(session_id, student_id) DO NOTHING
    """, (session_id, student[0]))
    if cursor.rowcount == 0:
        conn.close()
        raise ValueError("Attendance was already recorded for this class session. Contact your faculty if it needs correction.")
    _audit(cursor, user_id, "attendance.qr_marked", f"session={session_id}")
    conn.commit()
    conn.close()


# ============================================================
# GET STUDENT PROFILE
# ============================================================

def get_student_profile(user_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            user_id,
            roll_number,
            name,
            department,
            year,
            section,
            class_id
        FROM students
        WHERE user_id = ?
    """, (
        user_id,
    ))

    student = cursor.fetchone()

    connection.close()

    return student


def get_student_academic_records(user_id: int):
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.code, s.name, a.internal_mark, a.assignment_mark, a.lab_mark, a.total_mark
        FROM students st
        JOIN academics a ON a.student_id = st.id
        JOIN subjects s ON s.id = a.subject_id
        JOIN (SELECT DISTINCT class_id, subject_id FROM teaching_assignments) ta
            ON ta.class_id = st.class_id AND ta.subject_id = s.id
        WHERE st.user_id = ?
        ORDER BY s.code
    """, (user_id,)).fetchall()
    conn.close()
    return rows


def get_academic_classes(*, faculty_id: int | None = None, student_user_id: int | None = None) -> list[tuple]:
    conn = get_connection()
    try:
        if student_user_id is not None:
            return conn.execute("""SELECT c.id, c.department, c.year_of_study, c.section,
                    c.academic_year, COUNT(st.id)
                FROM academic_classes c JOIN students st ON st.class_id = c.id
                WHERE st.user_id = ? GROUP BY c.id ORDER BY c.academic_year DESC, c.department, c.year_of_study, c.section""",
                (student_user_id,)).fetchall()
        if faculty_id is not None:
            role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
            if not role or role[0] != "faculty":
                raise PermissionError("Only faculty can manage academic classes.")
            return conn.execute("""SELECT c.id, c.department, c.year_of_study, c.section,
                    c.academic_year, COUNT(st.id)
                FROM academic_classes c LEFT JOIN students st ON st.class_id = c.id
                WHERE c.created_by = ? OR EXISTS (SELECT 1 FROM teaching_assignments ta
                    WHERE ta.class_id = c.id AND ta.faculty_id = ?)
                GROUP BY c.id ORDER BY c.academic_year DESC, c.department, c.year_of_study, c.section""",
                (faculty_id, faculty_id)).fetchall()
        return conn.execute("""SELECT c.id, c.department, c.year_of_study, c.section,
                c.academic_year, COUNT(st.id)
            FROM academic_classes c LEFT JOIN students st ON st.class_id = c.id
            GROUP BY c.id ORDER BY c.academic_year DESC, c.department, c.year_of_study, c.section""").fetchall()
    finally:
        conn.close()


def get_student_class_id(user_id: int) -> int | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT class_id FROM students WHERE user_id = ?", (user_id,)).fetchone()
        return int(row[0]) if row and row[0] is not None else None
    finally:
        conn.close()


def create_academic_class(faculty_id: int, department: str, year: int, section: str,
                          academic_year: str) -> int:
    department, section, academic_year = (str(value or "").strip()
                                          for value in (department, section, academic_year))
    try:
        year = int(year)
    except (TypeError, ValueError) as error:
        raise ValueError("Choose a valid year of study.") from error
    if not department or not section or not academic_year:
        raise ValueError("Department, academic year, and class section are required.")
    if not 1 <= year <= 8:
        raise ValueError("Year of study must be between 1 and 8.")
    if len(academic_year) != 9 or academic_year[4] != "-" or not academic_year[:4].isdigit() or not academic_year[5:].isdigit():
        raise ValueError("Academic year must use YYYY-YYYY format, such as 2026-2027.")
    if int(academic_year[5:]) != int(academic_year[:4]) + 1:
        raise ValueError("The end year must be one year after the start year.")
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can create an academic class.")
        class_id = _get_or_create_academic_class(conn.cursor(), department, year, section, academic_year)
        conn.execute("UPDATE academic_classes SET created_by = COALESCE(created_by, ?) WHERE id = ?",
                     (faculty_id, class_id))
        _audit(conn.cursor(), faculty_id, "academic_class.created",
               f"class={class_id}; dept={department}; year={year}; section={section}; academic_year={academic_year}")
        conn.commit()
        return class_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_faculty_directory(actor_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (actor_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can view teaching staff.")
        return conn.execute("""SELECT u.id, u.name, fp.employee_code, fp.department, fp.designation
            FROM users u LEFT JOIN faculty_profiles fp ON fp.user_id = u.id
            WHERE u.role = 'faculty' ORDER BY u.name""").fetchall()
    finally:
        conn.close()


def update_faculty_profile(faculty_id: int, employee_code: str, department: str,
                           designation: str) -> None:
    employee_code, department, designation = (str(value or "").strip()
                                               for value in (employee_code, department, designation))
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can update a faculty profile.")
        conn.execute("""INSERT INTO faculty_profiles(user_id, employee_code, department, designation)
            VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET employee_code=excluded.employee_code,
            department=excluded.department, designation=excluded.designation""",
            (faculty_id, employee_code or None, department, designation or "Faculty"))
        _audit(conn.cursor(), faculty_id, "faculty_profile.updated", f"department={department}; designation={designation}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def assign_subject_to_class(actor_id: int, class_id: int, subject_id: int,
                            faculty_id: int, academic_term: str = "Full Year") -> int:
    term = str(academic_term or "").strip() or "Full Year"
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (actor_id,)).fetchone()
        target = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty" or not target or target[0] != "faculty":
            raise PermissionError("Only faculty accounts can manage teaching assignments.")
        if not conn.execute("SELECT 1 FROM academic_classes WHERE id = ?", (class_id,)).fetchone():
            raise ValueError("Choose a valid academic class.")
        if not conn.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
            raise ValueError("Choose a valid subject.")
        conn.execute("""INSERT INTO teaching_assignments(class_id, subject_id, faculty_id, academic_term)
            VALUES (?, ?, ?, ?) ON CONFLICT(class_id, subject_id, academic_term)
            DO UPDATE SET faculty_id=excluded.faculty_id""",
            (class_id, subject_id, faculty_id, term))
        row = conn.execute("""SELECT id FROM teaching_assignments
            WHERE class_id=? AND subject_id=? AND academic_term=?""", (class_id, subject_id, term)).fetchone()
        _audit(conn.cursor(), actor_id, "teaching_assignment.saved",
               f"assignment={row[0]}; class={class_id}; subject={subject_id}; faculty={faculty_id}")
        conn.commit()
        return int(row[0])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_class_subjects(class_id: int, *, faculty_id: int | None = None) -> list[tuple]:
    conn = get_connection()
    try:
        sql = """SELECT s.id, s.code, s.name, ta.faculty_id, u.name, ta.academic_term
            FROM teaching_assignments ta JOIN subjects s ON s.id=ta.subject_id
            JOIN users u ON u.id=ta.faculty_id WHERE ta.class_id=?"""
        params: tuple = (class_id,)
        if faculty_id is not None:
            sql += " AND ta.faculty_id=?"
            params = (class_id, faculty_id)
        return conn.execute(sql + " ORDER BY s.code", params).fetchall()
    finally:
        conn.close()


def get_all_academic_records(faculty_id: int, class_id: int | None = None):
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can view all academic records.")
        query = """
            SELECT st.id, st.roll_number, st.name, s.id, s.code, s.name,
                   a.internal_mark, a.assignment_mark, a.lab_mark, a.total_mark,
                   st.class_id, c.department, c.year_of_study, c.section, c.academic_year
            FROM students st
        JOIN (SELECT DISTINCT class_id, subject_id, faculty_id FROM teaching_assignments) ta
            ON ta.class_id = st.class_id AND ta.faculty_id = ?
            JOIN subjects s ON s.id = ta.subject_id
            LEFT JOIN academic_classes c ON c.id = st.class_id
            LEFT JOIN academics a ON a.student_id = st.id AND a.subject_id = s.id
        """
        params: tuple = (faculty_id,)
        if class_id is not None:
            query += " WHERE st.class_id = ?"
            params = (faculty_id, class_id)
        return conn.execute(query + " ORDER BY c.year_of_study, c.section, st.roll_number, s.code", params).fetchall()
    finally:
        conn.close()


def save_academic_record(student_id: int, subject_id: int, internal_mark: float,
                         assignment_mark: float, lab_mark: float, faculty_id: int) -> None:
    marks = (internal_mark, assignment_mark, lab_mark)
    if any(mark < 0 or mark > 100 for mark in marks):
        raise ValueError("Each mark must be between 0 and 100.")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = cursor.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can update academic records.")
    assigned = cursor.execute("""SELECT 1 FROM students st
        JOIN (SELECT DISTINCT class_id, subject_id, faculty_id FROM teaching_assignments) ta ON ta.class_id = st.class_id
        WHERE st.id = ? AND ta.subject_id = ? AND ta.faculty_id = ?""",
        (student_id, subject_id, faculty_id)).fetchone()
    if not assigned:
        conn.close()
        raise PermissionError("This subject is not assigned to you for the student's class.")
    total = round(sum(marks), 2)
    cursor.execute("""
        INSERT INTO academics (student_id, subject_id, internal_mark, assignment_mark, lab_mark, total_mark)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id, subject_id) DO UPDATE SET
            internal_mark = excluded.internal_mark,
            assignment_mark = excluded.assignment_mark,
            lab_mark = excluded.lab_mark,
            total_mark = excluded.total_mark
    """, (student_id, subject_id, *marks, total))
    _audit(cursor, faculty_id, "academics.saved", f"student={student_id}; subject={subject_id}")
    conn.commit()
    conn.close()


# ============================================================
# GET STUDENT ATTENDANCE SUMMARY
# ============================================================

def get_student_attendance(user_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            s.code,
            s.name,

            COUNT(DISTINCT ats.id) AS total_classes,

            COALESCE(
                SUM(
                    CASE
                        WHEN ar.status = 'Present'
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS present_classes

        FROM students st

        JOIN (SELECT DISTINCT class_id, subject_id FROM teaching_assignments) ta ON ta.class_id = st.class_id
        JOIN subjects s ON s.id = ta.subject_id

        LEFT JOIN attendance_sessions ats
            ON ats.subject_id = s.id
            AND (ats.class_id = st.class_id OR (ats.class_id IS NULL AND ats.section = st.section))

        LEFT JOIN attendance_records ar
            ON ar.session_id = ats.id AND ar.student_id = st.id

        WHERE st.user_id = ?

        GROUP BY
            s.id,
            s.code,
            s.name

        ORDER BY s.code
    """, (
        user_id,
    ))

    rows = cursor.fetchall()

    connection.close()

    return rows


# ============================================================
# GET STUDENT ATTENDANCE HISTORY
# ============================================================

def get_student_attendance_history(user_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            ats.class_date,
            s.code,
            s.name,
            COALESCE(ar.status, 'Absent') AS status,
            COALESCE(ar.verification_method, 'not recorded') AS verification_method

        FROM students st

        INNER JOIN attendance_sessions ats
            ON ats.class_id = st.class_id OR (ats.class_id IS NULL AND ats.section = st.section)

        LEFT JOIN attendance_records ar
            ON ar.session_id = ats.id AND ar.student_id = st.id

        INNER JOIN subjects s
            ON s.id = ats.subject_id

        WHERE st.user_id = ?

        ORDER BY
            ats.class_date DESC,
            s.code
    """, (
        user_id,
    ))

    rows = cursor.fetchall()

    connection.close()

    return rows


# ============================================================
# NEW FEATURE HELPER FUNCTIONS
# ============================================================

def get_timetables(*, faculty_id: int | None = None, student_user_id: int | None = None,
                   class_id: int | None = None):
    conn = get_connection()
    try:
        if student_user_id is not None:
            student = conn.execute("SELECT class_id FROM students WHERE user_id = ?", (student_user_id,)).fetchone()
            if not student:
                raise PermissionError("A student account is required to view a timetable.")
            class_id = student[0]
        sql = """SELECT t.id, s.code, s.name, t.day_of_week, t.start_time, t.end_time,
                t.room, t.faculty_id, t.class_id, c.department, c.year_of_study, c.section, c.academic_year
        FROM timetables t
        JOIN subjects s ON s.id = t.subject_id
        LEFT JOIN academic_classes c ON c.id = t.class_id"""
        conditions, params = [], []
        if faculty_id is not None:
            conditions.append("t.faculty_id = ?")
            params.append(faculty_id)
        if student_user_id is not None or class_id is not None:
            conditions.append("(t.class_id = ? OR (t.class_id IS NULL AND ? IS NOT NULL))")
            params.append(class_id)
            params.append(class_id)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        return conn.execute(sql + " ORDER BY t.day_of_week, t.start_time", tuple(params)).fetchall()
    finally:
        conn.close()


def _validate_timetable_values(day_of_week: str, start_time: str, end_time: str, room: str) -> None:
    from datetime import datetime
    if day_of_week not in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"):
        raise ValueError("Choose a valid day of the week.")
    try:
        start = datetime.strptime(start_time, "%H:%M").time()
        end = datetime.strptime(end_time, "%H:%M").time()
    except (TypeError, ValueError) as error:
        raise ValueError("Enter timetable times in HH:MM format.") from error
    if end <= start:
        raise ValueError("The class end time must be later than the start time.")
    if not room.strip():
        raise ValueError("Enter a classroom or laboratory location.")


def add_timetable_entry(subject_id: int, day_of_week: str, start_time: str, end_time: str,
                        room: str, faculty_id: int, class_id: int | None = None) -> int:
    _validate_timetable_values(day_of_week, start_time, end_time, room)
    conn = get_connection()
    c = conn.cursor()
    try:
        role = c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can manage the timetable.")
        if not c.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
            raise ValueError("Choose a valid subject.")
        if class_id is None or not c.execute("""SELECT 1 FROM teaching_assignments
            WHERE class_id=? AND subject_id=? AND faculty_id=?""", (class_id, subject_id, faculty_id)).fetchone():
            raise PermissionError("Choose a class and subject assigned to your faculty account.")
        overlap = c.execute("""SELECT 1 FROM timetables
            WHERE day_of_week = ? AND start_time < ? AND end_time > ?
              AND (faculty_id = ? OR room = ? COLLATE NOCASE) LIMIT 1""",
            (day_of_week, end_time, start_time, faculty_id, room.strip())).fetchone()
        if overlap:
            raise ValueError("This time conflicts with another class for the faculty member or room.")
        c.execute("""INSERT INTO timetables (subject_id, day_of_week, start_time, end_time, room, faculty_id, class_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (subject_id, day_of_week, start_time, end_time, room.strip(), faculty_id, class_id))
        entry_id = c.lastrowid
        _audit(c, faculty_id, "timetable.created", f"entry={entry_id}; day={day_of_week}; room={room.strip()}")
        conn.commit()
        return entry_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_timetable_entry(entry_id: int, subject_id: int, day_of_week: str, start_time: str,
                           end_time: str, room: str, faculty_id: int, class_id: int | None = None) -> None:
    _validate_timetable_values(day_of_week, start_time, end_time, room)
    conn = get_connection()
    c = conn.cursor()
    try:
        role = c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        owner = c.execute("SELECT faculty_id FROM timetables WHERE id = ?", (entry_id,)).fetchone()
        if not role or role[0] != "faculty" or not owner or owner[0] != faculty_id:
            raise PermissionError("You can update only your own timetable entries.")
        if not c.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
            raise ValueError("Choose a valid subject.")
        if class_id is None or not c.execute("""SELECT 1 FROM teaching_assignments
            WHERE class_id=? AND subject_id=? AND faculty_id=?""", (class_id, subject_id, faculty_id)).fetchone():
            raise PermissionError("Choose a class and subject assigned to your faculty account.")
        overlap = c.execute("""SELECT 1 FROM timetables
            WHERE id <> ? AND day_of_week = ? AND start_time < ? AND end_time > ?
              AND (faculty_id = ? OR room = ? COLLATE NOCASE) LIMIT 1""",
            (entry_id, day_of_week, end_time, start_time, faculty_id, room.strip())).fetchone()
        if overlap:
            raise ValueError("This time conflicts with another class for the faculty member or room.")
        c.execute("""UPDATE timetables SET subject_id = ?, day_of_week = ?, start_time = ?,
            end_time = ?, room = ?, class_id = ? WHERE id = ?""",
            (subject_id, day_of_week, start_time, end_time, room.strip(), class_id, entry_id))
        _audit(c, faculty_id, "timetable.updated", f"entry={entry_id}; day={day_of_week}; room={room.strip()}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_timetable_entry(entry_id: int, faculty_id: int) -> None:
    conn = get_connection()
    c = conn.cursor()
    try:
        role = c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        owner = c.execute("SELECT faculty_id FROM timetables WHERE id = ?", (entry_id,)).fetchone()
        if not role or role[0] != "faculty" or not owner or owner[0] != faculty_id:
            raise PermissionError("You can delete only your own timetable entries.")
        c.execute("DELETE FROM timetables WHERE id = ?", (entry_id,))
        _audit(c, faculty_id, "timetable.deleted", f"entry={entry_id}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_assignments(*, faculty_id: int | None = None, student_user_id: int | None = None,
                    class_id: int | None = None):
    conn = get_connection()
    try:
        if student_user_id is not None:
            student = conn.execute("SELECT class_id FROM students WHERE user_id = ?", (student_user_id,)).fetchone()
            if not student:
                raise PermissionError("A student account is required to view assignments.")
            class_id = student[0]
        sql = """SELECT a.id, s.code, s.name, a.title, a.description, a.due_date, a.max_marks,
                a.class_id, c.department, c.year_of_study, c.section, c.academic_year
        FROM assignments a
        JOIN subjects s ON s.id = a.subject_id
        LEFT JOIN academic_classes c ON c.id = a.class_id
        """
        conditions, params = [], []
        if faculty_id is not None:
            conditions.append("(a.faculty_id = ? OR a.class_id IN (SELECT class_id FROM teaching_assignments WHERE faculty_id = ?))")
            params.extend((faculty_id, faculty_id))
        if student_user_id is not None:
            conditions.append("(a.class_id IS NULL OR a.class_id = ?)")
            params.append(class_id)
        elif class_id is not None:
            conditions.append("(a.class_id IS NULL OR a.class_id = ?)")
            params.append(class_id)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        return conn.execute(sql + " ORDER BY a.due_date", tuple(params)).fetchall()
    finally:
        conn.close()


def add_assignment(subject_id, title, description, due_date, faculty_id=None, class_id=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can publish assignments.")
    if class_id is None:
        choices = c.execute("SELECT class_id FROM teaching_assignments WHERE subject_id=? AND faculty_id=?",
                            (subject_id, faculty_id)).fetchall()
        if len(choices) == 1:
            class_id = choices[0][0]
    if class_id is None:
        conn.close()
        raise ValueError("Choose the class this assignment is for.")
    if not c.execute("SELECT 1 FROM teaching_assignments WHERE class_id=? AND subject_id=? AND faculty_id=?",
                     (class_id, subject_id, faculty_id)).fetchone():
        conn.close()
        raise PermissionError("This subject is not assigned to you for the selected class.")
    c.execute("""INSERT INTO assignments (subject_id, title, description, due_date, faculty_id, class_id)
        VALUES (?, ?, ?, ?, ?, ?)""", (subject_id, title, description, due_date, faculty_id, class_id))
    _audit(c, faculty_id, "assignment.created", f"assignment={c.lastrowid}; title={title}")
    conn.commit()
    conn.close()


def get_notes(*, student_user_id: int | None = None, class_id: int | None = None,
              faculty_id: int | None = None):
    conn = get_connection()
    try:
        if student_user_id is not None:
            student = conn.execute("SELECT class_id FROM students WHERE user_id = ?", (student_user_id,)).fetchone()
            if not student:
                raise PermissionError("A student account is required to view course notes.")
            class_id = student[0]
        sql = """SELECT n.id, s.code, s.name, n.unit_number, n.title, n.file_path, n.created_at,
                n.class_id, n.uploaded_by
            FROM notes n JOIN subjects s ON s.id = n.subject_id"""
        conditions, params = [], []
        if student_user_id is not None:
            conditions.append("(n.class_id IS NULL OR n.class_id = ?)")
            params.append(class_id)
        elif class_id is not None:
            conditions.append("(n.class_id IS NULL OR n.class_id = ?)")
            params.append(class_id)
        if faculty_id is not None:
            conditions.append("(n.uploaded_by = ? OR n.uploaded_by IS NULL)")
            params.append(faculty_id)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        return conn.execute(sql + " ORDER BY s.code, n.unit_number", tuple(params)).fetchall()
    finally:
        conn.close()


def add_note(subject_id, title, file_path, unit_number=1, uploaded_by=None, class_id=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (uploaded_by,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can upload course notes.")
    if class_id is None:
        choices = c.execute("SELECT class_id FROM teaching_assignments WHERE subject_id=? AND faculty_id=?",
                            (subject_id, uploaded_by)).fetchall()
        if len(choices) == 1:
            class_id = choices[0][0]
    if class_id is None or not c.execute("""SELECT 1 FROM teaching_assignments
        WHERE class_id=? AND subject_id=? AND faculty_id=?""", (class_id, subject_id, uploaded_by)).fetchone():
        conn.close()
        raise PermissionError("Choose a class and subject assigned to your faculty account.")
    c.execute("""INSERT INTO notes (subject_id, title, file_path, unit_number, uploaded_by, class_id)
        VALUES (?, ?, ?, ?, ?, ?)""", (subject_id, title, file_path, unit_number, uploaded_by, class_id))
    _audit(c, uploaded_by, "note.uploaded", f"title={title}")
    conn.commit()
    conn.close()


def delete_course_document(note_id: int, faculty_id: int) -> None:
    """Delete a course note and its search index; remove its upload if unused."""
    from storage.local_storage import STORAGE_PREFIX, storage_service

    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can delete course documents.")
        note = conn.execute("SELECT title, file_path FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not note:
            raise ValueError("This course document no longer exists.")
        title, file_path = note
        conn.execute("DELETE FROM documents WHERE file_path = ? AND title = ?", (file_path, title))
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        referenced = conn.execute(
            "SELECT 1 FROM notes WHERE file_path = ? UNION ALL "
            "SELECT 1 FROM documents WHERE file_path = ? LIMIT 1",
            (file_path, file_path),
        ).fetchone()
        _audit(conn.cursor(), faculty_id, "course_document.deleted", f"note={note_id}; title={title}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if file_path.startswith(STORAGE_PREFIX) and not referenced:
        storage_service.remove(file_path)


def get_question_banks(*, student_user_id: int | None = None, faculty_id: int | None = None,
                       class_id: int | None = None):
    conn = get_connection()
    try:
        if student_user_id is not None:
            student = conn.execute("SELECT class_id FROM students WHERE user_id = ?", (student_user_id,)).fetchone()
            if not student:
                raise PermissionError("A student account is required to view the question bank.")
            class_id = student[0]
        sql = """
        SELECT q.id, s.code, s.name, q.unit_number, q.question, q.answer_key,
               q.difficulty, q.marks, q.source_kind, q.exam_year, q.class_id
        FROM question_banks q
        JOIN subjects s ON s.id = q.subject_id
        """
        conditions, params = [], []
        if student_user_id is not None or class_id is not None:
            conditions.append("(q.class_id IS NULL OR q.class_id = ?)")
            params.append(class_id)
        if faculty_id is not None:
            conditions.append("(q.class_id IS NULL OR q.class_id IN (SELECT class_id FROM teaching_assignments WHERE faculty_id = ?))")
            params.append(faculty_id)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        return conn.execute(sql + " ORDER BY s.code, q.unit_number", tuple(params)).fetchall()
    finally:
        conn.close()


def get_lab_experiments(*, faculty_id: int | None = None, student_user_id: int | None = None,
                        class_id: int | None = None) -> list[tuple]:
    """List lab manuals visible to one assigned faculty member or enrolled student."""
    conn = get_connection()
    try:
        conditions, params = [], []
        if faculty_id is not None:
            role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
            if not role or role[0] != "faculty":
                raise PermissionError("Only faculty can manage lab manuals.")
            conditions.append("(e.class_id IS NULL OR e.class_id IN "
                              "(SELECT class_id FROM teaching_assignments WHERE faculty_id = ?))")
            params.append(faculty_id)
        if student_user_id is not None:
            student = conn.execute("SELECT role FROM users WHERE id = ?", (student_user_id,)).fetchone()
            if not student or student[0] != "student":
                raise PermissionError("A student account is required to view lab manuals.")
            conditions.append("(e.class_id IS NULL OR e.class_id = "
                              "(SELECT class_id FROM students WHERE user_id = ?))")
            params.append(student_user_id)
        if class_id is not None:
            conditions.append("e.class_id = ?")
            params.append(class_id)
        query = """SELECT e.id, s.code, s.name, e.exp_number, e.title, e.description,
                e.manual_path, e.class_id, c.department, c.year_of_study, c.section,
                c.academic_year
            FROM lab_experiments e JOIN subjects s ON s.id = e.subject_id
            LEFT JOIN academic_classes c ON c.id = e.class_id"""
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        return conn.execute(query + " ORDER BY s.code, e.exp_number, e.id", tuple(params)).fetchall()
    finally:
        conn.close()


def create_lab_experiment(faculty_id: int, class_id: int, subject_id: int,
                          exp_number: int, title: str, description: str,
                          manual_file: str | None = None) -> int:
    """Create an assigned, class-scoped lab and optionally store its reference manual."""
    title = str(title or "").strip()
    description = str(description or "").strip()
    try:
        exp_number = int(exp_number)
    except (TypeError, ValueError) as error:
        raise ValueError("Enter a valid experiment number.") from error
    if not title or len(title) > 200:
        raise ValueError("Enter an experiment title of 1 to 200 characters.")
    if not description:
        raise ValueError("Add experiment instructions before publishing.")
    if not 1 <= exp_number <= 1000:
        raise ValueError("Experiment number must be between 1 and 1000.")

    conn = get_connection()
    stored_manual = None
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can publish lab experiments.")
        assigned = conn.execute("""SELECT 1 FROM teaching_assignments
            WHERE class_id = ? AND subject_id = ? AND faculty_id = ?""",
            (class_id, subject_id, faculty_id)).fetchone()
        if not assigned:
            raise PermissionError("Choose a class and subject assigned to your faculty account.")
        duplicate = conn.execute("""SELECT 1 FROM lab_experiments
            WHERE class_id = ? AND subject_id = ? AND exp_number = ?""",
            (class_id, subject_id, exp_number)).fetchone()
        if duplicate:
            raise ValueError("That experiment number already exists for this class and subject.")
        if manual_file:
            from storage.local_storage import storage_service
            stored_manual = storage_service.store_file(
                manual_file, uploaded_by=faculty_id, category="lab_manuals",
                allowed_extensions={".pdf", ".txt", ".md"},
            )
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO lab_experiments
            (subject_id, exp_number, title, description, manual_path, class_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (subject_id, exp_number, title, description, stored_manual, class_id))
        experiment_id = cursor.lastrowid
        _audit(cursor, faculty_id, "lab_experiment.published",
               f"experiment={experiment_id}; class={class_id}; subject={subject_id}")
        conn.commit()
        return int(experiment_id)
    except Exception:
        conn.rollback()
        if stored_manual:
            from storage.local_storage import storage_service
            storage_service.remove(stored_manual)
        raise
    finally:
        conn.close()


def get_lab_experiment_progress(experiment_id: int, faculty_id: int) -> list[tuple]:
    """Show every enrolled student's progress for a lab assigned to this faculty member."""
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can view lab experiment progress.")
        experiment = conn.execute("SELECT class_id, subject_id FROM lab_experiments WHERE id = ?",
                                  (experiment_id,)).fetchone()
        if not experiment:
            raise ValueError("This lab experiment no longer exists.")
        class_id, subject_id = experiment
        assignment_query = "SELECT 1 FROM teaching_assignments WHERE subject_id = ? AND faculty_id = ?"
        assignment_params = [subject_id, faculty_id]
        if class_id is not None:
            assignment_query += " AND class_id = ?"
            assignment_params.append(class_id)
        assignment = conn.execute(assignment_query, tuple(assignment_params)).fetchone()
        if not assignment:
            raise PermissionError("This lab is not assigned to your faculty account.")
        if class_id is None:
            return conn.execute("""SELECT st.id, st.roll_number, st.name,
                    COALESCE(sub.status, 'Not started'), sub.code_snippet, sub.completed_at, sub.id
                FROM students st JOIN teaching_assignments ta
                    ON ta.class_id = st.class_id AND ta.subject_id = ? AND ta.faculty_id = ?
                LEFT JOIN lab_submissions sub ON sub.experiment_id = ? AND sub.student_id = st.id
                ORDER BY st.roll_number""", (subject_id, faculty_id, experiment_id)).fetchall()
        return conn.execute("""SELECT st.id, st.roll_number, st.name,
                COALESCE(sub.status, 'Not started'), sub.code_snippet, sub.completed_at, sub.id
            FROM students st LEFT JOIN lab_submissions sub
                ON sub.experiment_id = ? AND sub.student_id = st.id
            WHERE st.class_id = ? ORDER BY st.roll_number""",
            (experiment_id, class_id)).fetchall()
    finally:
        conn.close()


def get_lab_exams():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT e.id, s.code, s.name, e.title, e.question_paper_text, e.duration_minutes, e.is_active
        FROM lab_exams e
        JOIN subjects s ON s.id = e.subject_id
        WHERE e.is_active = 1
        ORDER BY e.id DESC
        LIMIT 1
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def get_announcements(role: str | None = None, *, user_id: int | None = None,
                     class_id: int | None = None):
    conn = get_connection()
    query = """
        SELECT a.id, u.name, a.title, a.content, a.target_group, a.created_at,
               a.class_id, c.department, c.year_of_study, c.section, c.academic_year
        FROM announcements a
        JOIN users u ON u.id = a.faculty_id
        LEFT JOIN academic_classes c ON c.id = a.class_id
    """
    conditions, params = [], []
    if role == "student":
        conditions.append("a.target_group IN ('All', 'Students')")
        if user_id is not None:
            student = conn.execute("SELECT class_id FROM students WHERE user_id = ?", (user_id,)).fetchone()
            class_id = student[0] if student else None
        if class_id is not None:
            conditions.append("(a.class_id IS NULL OR a.class_id = ?)")
            params.append(class_id)
        else:
            conditions.append("a.class_id IS NULL")
    elif role == "faculty" and user_id is not None:
        conditions.append("(a.faculty_id = ? OR a.class_id IN (SELECT class_id FROM teaching_assignments WHERE faculty_id = ?))")
        params.extend((user_id, user_id))
    if class_id is not None and role != "student":
        conditions.append("(a.class_id IS NULL OR a.class_id = ?)")
        params.append(class_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    try:
        return conn.execute(query + " ORDER BY a.created_at DESC", tuple(params)).fetchall()
    finally:
        conn.close()


def add_announcement(faculty_id, title, content, target_group="All", class_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can publish announcements.")
    if class_id is not None and not c.execute("SELECT 1 FROM academic_classes WHERE id = ?", (class_id,)).fetchone():
        conn.close()
        raise ValueError("Choose a valid academic class.")
    if class_id is not None and not c.execute("""SELECT 1 FROM academic_classes c
        WHERE c.id=? AND (c.created_by=? OR EXISTS (SELECT 1 FROM teaching_assignments ta
        WHERE ta.class_id=c.id AND ta.faculty_id=?))""", (class_id, faculty_id, faculty_id)).fetchone():
        conn.close()
        raise PermissionError("Post notices only to a class you created or teach.")
    c.execute("INSERT INTO announcements (faculty_id, title, content, target_group, class_id) VALUES (?, ?, ?, ?, ?)",
              (faculty_id, title, content, target_group, class_id))
    _audit(c, faculty_id, "announcement.created", f"title={title}; audience={target_group}; class={class_id}")
    conn.commit()
    conn.close()


def get_reminders(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, title, reminder_type, due_date, is_completed
        FROM reminders
        WHERE user_id = ?
        ORDER BY due_date
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def add_reminder(user_id, title, reminder_type, due_date):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO reminders (user_id, title, reminder_type, due_date) VALUES (?, ?, ?, ?)",
              (user_id, title, reminder_type, due_date))
    _audit(c, user_id, "reminder.created", f"title={title}; due={due_date}")
    conn.commit()
    conn.close()


def search_faq(query):
    conn = get_connection()
    c = conn.cursor()
    q = f"%{query}%"
    c.execute("""
        SELECT category, question, answer
        FROM faq_knowledge_base
        WHERE question LIKE ? OR keywords LIKE ? OR answer LIKE ?
    """, (q, q, q))
    rows = c.fetchall()
    conn.close()
    return rows


def get_attendance_analytics(start_date: str | None = None, end_date: str | None = None,
                             subject_id: int | None = None, section: str | None = None,
                             class_id: int | None = None, faculty_id: int | None = None):
    if start_date:
        date.fromisoformat(start_date)
    if end_date:
        date.fromisoformat(end_date)
    if start_date and end_date and start_date > end_date:
        raise ValueError("The report start date must be on or before the end date.")
    conn = get_connection()
    c = conn.cursor()
    session_filters, params = [], []
    student_filters, student_params = [], []
    for clause, value in (("ats.class_date >= ?", start_date), ("ats.class_date <= ?", end_date),
                          ("ats.subject_id = ?", subject_id), ("ats.section = ?", section)):
        if value is not None:
            session_filters.append(clause)
            params.append(value)
    if class_id is not None:
        student_filters.append("st.class_id = ?")
        student_params.append(class_id)
    if faculty_id is not None:
        student_filters.append("(EXISTS (SELECT 1 FROM teaching_assignments ta WHERE ta.class_id=st.class_id AND ta.faculty_id=?) OR EXISTS (SELECT 1 FROM academic_classes c WHERE c.id=st.class_id AND c.created_by=?))")
        student_params.append(faculty_id)
        student_params.append(faculty_id)
    query = """
        SELECT
            st.roll_number,
            st.name,
            COUNT(DISTINCT ats.id) as total_sessions,
            COALESCE(SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END), 0) as present_count,
            ROUND(CAST(COALESCE(SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END), 0) AS NUMERIC) /
                  CASE WHEN COUNT(DISTINCT ats.id) < 1 THEN 1 ELSE COUNT(DISTINCT ats.id) END * 100, 1) as percentage
        FROM students st
        LEFT JOIN attendance_sessions ats ON
            (ats.class_id = st.class_id OR (ats.class_id IS NULL AND ats.section = st.section))
    """
    if session_filters:
        query += " AND " + " AND ".join(session_filters)
    query += """
        LEFT JOIN attendance_records ar ON ar.session_id = ats.id AND ar.student_id = st.id
    """
    if student_filters:
        query += " WHERE " + " AND ".join(student_filters)
    query += """
        GROUP BY st.id, st.roll_number, st.name
        ORDER BY percentage ASC
    """
    c.execute(query, params + student_params)
    rows = c.fetchall()
    conn.close()
    return rows


def get_voice_notes(user_id: int) -> list[tuple]:
    """Return the current user's private notes, most recently updated first."""
    with closing(get_connection()) as shared, closing(get_local_connection()) as local:
        role = shared.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not role:
            raise PermissionError("Sign in to view your private notes.")
        return local.execute(
            "SELECT id, title, content, created_at, updated_at FROM voice_notes "
            "WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
            (user_id,),
        ).fetchall()


def save_voice_note(user_id: int, title: str, content: str, note_id: int | None = None) -> int:
    """Create or update a private note, refusing access to any other user's note."""
    title = title.strip()
    content = content.strip()
    if not title:
        raise ValueError("Enter a title for this note.")
    if len(title) > 160:
        raise ValueError("Note titles are limited to 160 characters.")
    if not content:
        raise ValueError("Enter some note text before saving.")
    if len(content) > 100_000:
        raise ValueError("Notes are limited to 100,000 characters.")
    with closing(get_connection()) as shared:
        role = shared.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not role:
            raise PermissionError("Sign in to save private notes.")
    with closing(get_local_connection()) as conn:
        if note_id is None:
            cursor = conn.execute(
                "INSERT INTO voice_notes (user_id, title, content) VALUES (?, ?, ?)",
                (user_id, title, content),
            )
            conn.commit()
            return cursor.lastrowid
        cursor = conn.execute(
            "UPDATE voice_notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ?",
            (title, content, note_id, user_id),
        )
        if cursor.rowcount != 1:
            raise PermissionError("That note does not belong to your account or no longer exists.")
        conn.commit()
        return note_id


def delete_voice_note(user_id: int, note_id: int) -> None:
    """Delete one of the current user's private notes and log the action."""
    with closing(get_local_connection()) as conn:
        cursor = conn.execute("DELETE FROM voice_notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        if cursor.rowcount != 1:
            raise PermissionError("That note does not belong to your account or no longer exists.")
        conn.commit()
    return rows


def record_assistant_query_event(category: str = "learning", *, user_id: int | None = None,
                                 class_id: int | None = None) -> None:
    if category not in ("learning", "schedule", "exam"):
        raise ValueError("Unknown assistant analytics category.")
    conn = get_connection()
    try:
        if class_id is None and user_id is not None:
            student = conn.execute("SELECT class_id FROM students WHERE user_id = ?", (user_id,)).fetchone()
            if student:
                class_id = student[0]
        conn.execute("INSERT INTO assistant_query_events(category, user_id, class_id) VALUES (?, ?, ?)",
                     (category, user_id, class_id))
        conn.execute("DELETE FROM assistant_query_events WHERE created_at < datetime('now', '-90 days')")
        conn.commit()
    finally:
        conn.close()


def get_classroom_activity_stats(faculty_id: int, class_id: int | None = None) -> dict:
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can view classroom activity analytics.")
        if class_id is not None and not conn.execute("""SELECT 1 FROM academic_classes c WHERE c.id=?
            AND (c.created_by=? OR EXISTS (SELECT 1 FROM teaching_assignments ta WHERE ta.faculty_id=? AND ta.class_id=c.id))""",
                                                      (class_id, faculty_id, faculty_id)).fetchone():
            raise PermissionError("This class is not assigned to your faculty account.")
        class_clause = "class_id = ?" if class_id is not None else "class_id IN (SELECT class_id FROM teaching_assignments WHERE faculty_id = ? UNION SELECT id FROM academic_classes WHERE created_by = ?)"
        class_params = (class_id,) if class_id is not None else (faculty_id, faculty_id)
        return {
            "learning_queries_today": conn.execute(
                f"SELECT COUNT(*) FROM assistant_query_events WHERE category = 'learning' AND date(created_at, 'localtime') = date('now', 'localtime') AND {class_clause}"
            , class_params).fetchone()[0],
            "schedule_queries_today": conn.execute(
                f"SELECT COUNT(*) FROM assistant_query_events WHERE category = 'schedule' AND date(created_at, 'localtime') = date('now', 'localtime') AND {class_clause}"
            , class_params).fetchone()[0],
            "exam_queries_today": conn.execute(
                f"SELECT COUNT(*) FROM assistant_query_events WHERE category = 'exam' AND date(created_at, 'localtime') = date('now', 'localtime') AND {class_clause}"
            , class_params).fetchone()[0],
            "lab_submissions_today": conn.execute(
                f"SELECT COUNT(*) FROM lab_submissions sub JOIN lab_experiments e ON e.id=sub.experiment_id JOIN students st ON st.id=sub.student_id WHERE date(sub.completed_at, 'localtime') = date('now', 'localtime') AND {('(st.class_id = ? AND (e.class_id = ? OR e.class_id IS NULL))' if class_id is not None else 'st.class_id IN (SELECT class_id FROM teaching_assignments WHERE faculty_id = ? UNION SELECT id FROM academic_classes WHERE created_by = ?)')}"
            , ((class_id, class_id) if class_id is not None else class_params)).fetchone()[0],
            "attendance_sessions_today": conn.execute(
                f"SELECT COUNT(*) FROM attendance_sessions WHERE class_date = CAST(date('now', 'localtime') AS TEXT) AND {class_clause}"
                , class_params).fetchone()[0],
            "assignment_submissions_today": conn.execute(
                f"SELECT COUNT(*) FROM assignment_submissions sub JOIN assignments a ON a.id=sub.assignment_id WHERE date(sub.submitted_at, 'localtime') = date('now', 'localtime') AND {('a.class_id = ?' if class_id is not None else 'a.class_id IN (SELECT class_id FROM teaching_assignments WHERE faculty_id = ? UNION SELECT id FROM academic_classes WHERE created_by = ?)')}"
            , class_params).fetchone()[0],
        }
    finally:
        conn.close()


def get_assignment_submissions(assignment_id: int, faculty_id: int):
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can view assignment submissions.")
        assigned = conn.execute("""SELECT 1 FROM assignments a
            JOIN teaching_assignments ta ON ta.class_id=a.class_id AND ta.subject_id=a.subject_id
            WHERE a.id=? AND ta.faculty_id=?""", (assignment_id, faculty_id)).fetchone()
        if not assigned:
            raise PermissionError("You can review submissions only for your assigned classes.")
        return conn.execute("""
            SELECT sub.id, st.roll_number, st.name, sub.submission_text, sub.file_path,
                   sub.submitted_at, sub.marks, sub.feedback, sub.graded_at
            FROM assignment_submissions sub
            JOIN students st ON st.id = sub.student_id
            WHERE sub.assignment_id = ?
            ORDER BY sub.submitted_at DESC
        """, (assignment_id,)).fetchall()
    finally:
        conn.close()


def get_student_lab_progress(user_id: int):
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not role or role[0] != "student":
            raise PermissionError("A student account is required to view personal lab progress.")
        return conn.execute("""SELECT e.id, s.code, s.name, e.exp_number, e.title, e.description,
            COALESCE(sub.status, 'Not started'), COALESCE(sub.code_snippet, ''), e.manual_path
            FROM lab_experiments e JOIN subjects s ON s.id = e.subject_id
            LEFT JOIN students st ON st.user_id = ? AND (e.class_id IS NULL OR e.class_id = st.class_id)
            LEFT JOIN lab_submissions sub ON sub.experiment_id = e.id AND sub.student_id = st.id
            WHERE e.class_id IS NULL OR e.class_id = st.class_id
            ORDER BY s.code, e.exp_number""", (user_id,)).fetchall()
    finally:
        conn.close()


def submit_lab_experiment(experiment_id: int, user_id: int, work_notes: str) -> None:
    if len(work_notes.strip()) < 20:
        raise ValueError("Add at least 20 characters describing your work before submitting.")
    conn = get_connection()
    try:
        student = conn.execute("SELECT st.id FROM students st JOIN users u ON u.id = st.user_id WHERE st.user_id = ? AND u.role = 'student'", (user_id,)).fetchone()
        if not student:
            raise PermissionError("A student account is required to submit lab work.")
        if not conn.execute("""SELECT 1 FROM lab_experiments e JOIN students st ON st.user_id = ?
            WHERE e.id = ? AND (e.class_id IS NULL OR e.class_id = st.class_id)""",
            (user_id, experiment_id)).fetchone():
            raise ValueError("Select a valid lab experiment.")
        previous = conn.execute("SELECT status FROM lab_submissions WHERE experiment_id = ? AND student_id = ?", (experiment_id, student[0])).fetchone()
        if previous and previous[0] == "Completed":
            raise ValueError("This experiment has already been approved as complete.")
        conn.execute("""INSERT INTO lab_submissions(experiment_id, student_id, code_snippet, status)
            VALUES (?, ?, ?, 'Submitted for Review')
            ON CONFLICT(experiment_id, student_id) DO UPDATE SET code_snippet = excluded.code_snippet,
                status = 'Submitted for Review', completed_at = CURRENT_TIMESTAMP""",
            (experiment_id, student[0], work_notes.strip()))
        _audit(conn.cursor(), user_id, "lab_work.submitted", f"experiment={experiment_id}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_lab_submission_reviews(faculty_id: int):
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can review student lab work.")
        return conn.execute("""SELECT sub.id, st.roll_number, st.name, s.code, e.title,
            sub.code_snippet, sub.completed_at, sub.status, e.id, e.class_id FROM lab_submissions sub
            JOIN students st ON st.id = sub.student_id JOIN lab_experiments e ON e.id = sub.experiment_id
            JOIN subjects s ON s.id = e.subject_id
            JOIN teaching_assignments ta ON ta.class_id = e.class_id AND ta.subject_id=e.subject_id
                AND ta.faculty_id = ?
            WHERE sub.status IN ('Submitted for Review','Needs Revision')
            ORDER BY sub.completed_at""", (faculty_id,)).fetchall()
    finally:
        conn.close()


def review_lab_submission(submission_id: int, faculty_id: int, decision: str) -> None:
    if decision not in ("Completed", "Needs Revision"):
        raise ValueError("Select an available review decision.")
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can review student lab work.")
        assigned = conn.execute("""SELECT 1 FROM lab_submissions sub
            JOIN lab_experiments e ON e.id = sub.experiment_id
            JOIN teaching_assignments ta ON ta.class_id = e.class_id
                AND ta.subject_id = e.subject_id AND ta.faculty_id = ?
            WHERE sub.id = ?""", (faculty_id, submission_id)).fetchone()
        if not assigned:
            raise PermissionError("You can review lab work only for a class and subject assigned to you.")
        cursor = conn.execute("UPDATE lab_submissions SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('Submitted for Review','Needs Revision')",
                              (decision, submission_id))
        if cursor.rowcount != 1:
            raise ValueError("This submission is no longer awaiting review.")
        _audit(conn.cursor(), faculty_id, "lab_work.reviewed", f"submission={submission_id}; decision={decision}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_lab_exam_catalog(faculty_id: int):
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can view the practical exam catalog.")
        return conn.execute("""SELECT e.id, s.code, s.name, e.title, e.duration_minutes, e.is_active, e.created_at
            FROM lab_exams e JOIN subjects s ON s.id = e.subject_id ORDER BY e.created_at DESC, e.id DESC""").fetchall()
    finally:
        conn.close()


def publish_lab_exam(subject_id: int, title: str, question_paper: str, duration_minutes: int, faculty_id: int) -> int:
    if not title.strip() or not question_paper.strip():
        raise ValueError("Enter an exam title and question paper.")
    if not 1 <= int(duration_minutes) <= 240:
        raise ValueError("Exam duration must be between 1 and 240 minutes.")
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can publish practical exams.")
        if not conn.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
            raise ValueError("Select a valid subject.")
        conn.execute("UPDATE lab_exams SET is_active = 0 WHERE is_active = 1")
        cursor = conn.execute("""INSERT INTO lab_exams(subject_id, title, question_paper_text, duration_minutes, is_active)
            VALUES (?, ?, ?, ?, 1)""", (subject_id, title.strip(), question_paper.strip(), int(duration_minutes)))
        _audit(conn.cursor(), faculty_id, "lab_exam.published", f"exam={cursor.lastrowid}; title={title.strip()}")
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_lab_exam(exam_id: int, faculty_id: int) -> bool:
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can close practical exams.")
        cursor = conn.execute("UPDATE lab_exams SET is_active = 0 WHERE id = ? AND is_active = 1", (exam_id,))
        if cursor.rowcount:
            _audit(conn.cursor(), faculty_id, "lab_exam.closed", f"exam={exam_id}")
            conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_lab_exam_submissions(exam_id: int, faculty_id: int):
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can view practical exam submissions.")
        return conn.execute("""SELECT st.roll_number, st.name, sub.started_at, sub.submitted_at,
            sub.solution_code FROM lab_exam_submissions sub JOIN students st ON st.id = sub.student_id
            WHERE sub.exam_id = ? ORDER BY st.roll_number""", (exam_id,)).fetchall()
    finally:
        conn.close()


def get_student_assignment_submission(assignment_id: int, user_id: int):
    conn = get_connection()
    row = conn.execute("""
        SELECT sub.submitted_at, sub.marks, sub.feedback, sub.submission_text,
               sub.file_path, sub.graded_at
        FROM assignment_submissions sub
        JOIN students st ON st.id = sub.student_id
        WHERE sub.assignment_id = ? AND st.user_id = ?
    """, (assignment_id, user_id)).fetchone()
    conn.close()
    return row


def submit_assignment(assignment_id: int, user_id: int, submission_text: str, file_path: str = ""):
    from storage.local_storage import STORAGE_PREFIX, storage_service

    conn = get_connection()
    try:
        student = conn.execute(
            "SELECT id FROM students WHERE user_id = ?", (user_id,)
        ).fetchone()
        assignment = conn.execute(
            "SELECT 1 FROM assignments WHERE id = ?", (assignment_id,)
        ).fetchone()
        if not student:
            return False
        if not assignment:
            raise ValueError("This assignment is no longer available.")
        previous = conn.execute(
            "SELECT file_path FROM assignment_submissions WHERE assignment_id = ? AND student_id = ?",
            (assignment_id, student[0]),
        ).fetchone()
        old_reference = previous[0] if previous else ""
    finally:
        conn.close()

    new_upload = False
    reference = file_path.strip()
    if reference:
        if reference.startswith(STORAGE_PREFIX):
            if not storage_service.owned_by(reference, user_id):
                raise PermissionError("That attachment does not belong to this student account.")
        else:
            reference = storage_service.store_file(
                reference, uploaded_by=user_id, category="assignment_submissions"
            )
            new_upload = True

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO assignment_submissions
                (assignment_id, student_id, submission_text, file_path, marks, feedback, graded_at)
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ON CONFLICT(assignment_id, student_id) DO UPDATE SET
                submission_text = excluded.submission_text,
                file_path = excluded.file_path,
                submitted_at = CURRENT_TIMESTAMP,
                marks = NULL,
                feedback = NULL,
                graded_at = NULL
        """, (assignment_id, student[0], submission_text, reference))
        _audit(cursor, user_id, "assignment.submitted", f"assignment={assignment_id}; student={student[0]}")
        conn.commit()
    except Exception:
        conn.rollback()
        if new_upload:
            storage_service.remove(reference)
        raise
    finally:
        conn.close()

    if old_reference and old_reference != reference and old_reference.startswith(STORAGE_PREFIX):
        storage_service.remove(old_reference)
    return True


def grade_submission(submission_id: int, marks: float, feedback: str, faculty_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can grade assignment submissions.")
    c.execute("""
        SELECT a.max_marks, a.class_id, a.subject_id FROM assignment_submissions s
        JOIN assignments a ON a.id = s.assignment_id
        WHERE s.id = ?
    """, (submission_id,))
    assignment = c.fetchone()
    if not assignment:
        conn.close()
        raise ValueError("The submission could not be found.")
    assigned = c.execute("SELECT 1 FROM teaching_assignments WHERE class_id=? AND subject_id=? AND faculty_id=?",
                         (assignment[1], assignment[2], faculty_id)).fetchone()
    if not assigned:
        conn.close()
        raise PermissionError("You can grade submissions only for your assigned classes.")
    if marks < 0 or marks > assignment[0]:
        conn.close()
        raise ValueError("The score must be within the assignment’s mark limit.")
    c.execute("""
        UPDATE assignment_submissions
        SET marks = ?, feedback = ?, graded_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (marks, feedback, submission_id))
    _audit(c, faculty_id, "assignment.graded", f"submission={submission_id}; marks={marks}")
    conn.commit()
    conn.close()
    return True


def add_question_bank_item(subject_id: int, unit_number: int, question: str, answer_key: str,
                          difficulty: str = "Medium", marks: int = 5, faculty_id: int | None = None,
                          source_kind: str = "Model", exam_year: int | None = None,
                          class_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    try:
        role = c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can add question-bank items.")
        if class_id is None:
            choices = c.execute("SELECT class_id FROM teaching_assignments WHERE subject_id=? AND faculty_id=?",
                                (subject_id, faculty_id)).fetchall()
            if len(choices) == 1:
                class_id = choices[0][0]
        if class_id is None or not c.execute("""SELECT 1 FROM teaching_assignments
            WHERE class_id=? AND subject_id=? AND faculty_id=?""", (class_id, subject_id, faculty_id)).fetchone():
            raise PermissionError("Choose a class and subject assigned to your faculty account.")
        if source_kind not in ("Model", "Previous Year"):
            raise ValueError("Question source must be Model or Previous Year.")
        if source_kind == "Previous Year" and (exam_year is None or not 2000 <= int(exam_year) <= date.today().year):
            raise ValueError("Enter a valid exam year for a previous-year question.")
        if source_kind == "Model":
            exam_year = None
        c.execute("""INSERT INTO question_banks
            (subject_id, unit_number, question, answer_key, difficulty, marks, source_kind, exam_year, class_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (subject_id, unit_number, question, answer_key, difficulty, marks, source_kind, exam_year, class_id))
        _audit(c, faculty_id, "question_bank.created", f"question={c.lastrowid}; subject={subject_id}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return True


def toggle_reminder_completed(reminder_id: int, user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE reminders
        SET is_completed = CASE WHEN is_completed = 1 THEN 0 ELSE 1 END
        WHERE id = ? AND user_id = ?
    """, (reminder_id, user_id))
    if c.rowcount == 0:
        conn.close()
        return False
    _audit(c, user_id, "reminder.completed_toggled", f"reminder={reminder_id}")
    conn.commit()
    conn.close()
    return True


# ============================================================
# STUDENT MANAGEMENT CRUD
# ============================================================

def add_student(username: str, roll_number: str, name: str, department: str = "CSE", year: int = 3, section: str = "C", password: str = "student123", faculty_id: int | None = None, class_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
        role = c.fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can create student accounts.")
        if not password:
            raise ValueError("A temporary password is required.")
        if class_id is None:
            class_id = _get_or_create_academic_class(c, department, year, section)
        else:
            academic_class = c.execute("SELECT department, year_of_study, section FROM academic_classes WHERE id = ?", (class_id,)).fetchone()
            if not academic_class or (academic_class[0], int(academic_class[1]), academic_class[2]) != (department, int(year), section):
                raise ValueError("The selected academic class does not match the student details.")
            if not c.execute("""SELECT 1 FROM academic_classes cls WHERE cls.id=?
                AND (cls.created_by=? OR EXISTS (SELECT 1 FROM teaching_assignments ta WHERE ta.class_id=cls.id AND ta.faculty_id=?))""",
                             (class_id, faculty_id, faculty_id)).fetchone():
                raise PermissionError("Enroll students only in a class you created or teach.")
        c.execute("INSERT INTO users (username, password, role, name) VALUES (?, ?, 'student', ?)",
                  (username, hash_password(password), name))
        user_id = c.lastrowid
        c.execute("""
            INSERT INTO students (user_id, roll_number, name, department, year, section, class_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, roll_number, name, department, year, section, class_id))
        student_id = c.lastrowid
        _audit(c, faculty_id, "student.created", f"student={student_id}; username={username}")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e


def update_student(student_id: int, roll_number: str, name: str, department: str, year: int, section: str, faculty_id: int | None = None, class_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can update student records.")
    if class_id is None:
        prior = c.execute("SELECT class_id FROM students WHERE id = ?", (student_id,)).fetchone()
        session = None
        if prior and prior[0]:
            session = c.execute("SELECT academic_year FROM academic_classes WHERE id = ?", (prior[0],)).fetchone()
        class_id = _get_or_create_academic_class(c, department, year, section, session[0] if session else None)
    else:
        academic_class = c.execute("SELECT department, year_of_study, section FROM academic_classes WHERE id = ?", (class_id,)).fetchone()
        if not academic_class or (academic_class[0], int(academic_class[1]), academic_class[2]) != (department, int(year), section):
            conn.close()
            raise ValueError("The selected academic class does not match the student details.")
        if not c.execute("""SELECT 1 FROM academic_classes cls WHERE cls.id=?
            AND (cls.created_by=? OR EXISTS (SELECT 1 FROM teaching_assignments ta WHERE ta.class_id=cls.id AND ta.faculty_id=?))""",
                         (class_id, faculty_id, faculty_id)).fetchone():
            conn.close()
            raise PermissionError("Move students only into a class you created or teach.")
    c.execute("""
        UPDATE students
        SET roll_number = ?, name = ?, department = ?, year = ?, section = ?, class_id = ?
        WHERE id = ?
    """, (roll_number, name, department, year, section, class_id, student_id))
    # Update corresponding user record name as well
    c.execute("""
        UPDATE users
        SET name = ?
        WHERE id = (SELECT user_id FROM students WHERE id = ?)
    """, (name, student_id))
    _audit(c, faculty_id, "student.updated", f"student={student_id}")
    conn.commit()
    conn.close()
    return True


def delete_student(student_id: int, faculty_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can remove student records.")
    c.execute("SELECT user_id FROM students WHERE id = ?", (student_id,))
    row = c.fetchone()
    if row:
        user_id = row[0]
        _audit(c, faculty_id, "student.deleted", f"student={student_id}; user={user_id}")
        c.execute("DELETE FROM students WHERE id = ?", (student_id,))
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    conn.close()
    return True


# ============================================================
# LIVE DASHBOARD STATS
# ============================================================

def get_dashboard_stats_faculty(faculty_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    if faculty_id is None:
        c.execute("SELECT COUNT(*) FROM students")
    else:
        c.execute("""SELECT COUNT(*) FROM students st WHERE st.class_id IN (
            SELECT class_id FROM teaching_assignments WHERE faculty_id = ?
            UNION SELECT id FROM academic_classes WHERE created_by = ?)""", (faculty_id, faculty_id))
    total_students = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(ar.id), SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END)
        FROM attendance_records ar
        JOIN attendance_sessions ats ON ats.id = ar.session_id
        JOIN (SELECT DISTINCT class_id, subject_id, faculty_id FROM teaching_assignments) ta
            ON ta.class_id = ats.class_id AND ta.subject_id = ats.subject_id
        WHERE (? IS NULL OR ta.faculty_id = ?)
    """, (faculty_id, faculty_id))
    row = c.fetchone()
    total_recs, present_recs = row[0] or 0, row[1] or 0
    att_pct = round((present_recs / total_recs * 100), 1) if total_recs > 0 else None

    if faculty_id is None:
        c.execute("SELECT COUNT(*) FROM assignments")
    else:
        c.execute("SELECT COUNT(*) FROM assignments WHERE faculty_id = ?", (faculty_id,))
    total_assignments = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM announcements WHERE (? IS NULL OR faculty_id = ?)", (faculty_id, faculty_id))
    total_notices = c.fetchone()[0]

    conn.close()
    return {
        "total_students": total_students,
        "attendance_pct": att_pct,
        "attendance_records": total_recs,
        "total_assignments": total_assignments,
        "total_notices": total_notices
    }


def get_dashboard_stats_student(user_id: int):
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id, class_id, section FROM students WHERE user_id = ?", (user_id,))
    st = c.fetchone()
    if not st:
        conn.close()
        return {
            "attendance_pct": None, "attendance_records": 0,
            "pending_assignments": 0, "completed_labs": 0,
            "total_labs": 0, "lab_pct": 0, "academic_average": None,
        }
    student_id, class_id, section = st[0], st[1], st[2]

    c.execute("""
        SELECT COUNT(ar.id), SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END)
        FROM attendance_records ar JOIN attendance_sessions ats ON ats.id = ar.session_id
        WHERE ar.student_id = ? AND (ats.class_id = ? OR (ats.class_id IS NULL AND ats.section = ?))
    """, (student_id, class_id, section))
    row = c.fetchone()
    total_recs, present_recs = row[0] or 0, row[1] or 0
    att_pct = round((present_recs / total_recs * 100), 1) if total_recs > 0 else None

    c.execute("SELECT COUNT(*) FROM assignments WHERE class_id IS NULL OR class_id = ?", (class_id,))
    total_assignments = c.fetchone()[0]

    c.execute("""SELECT COUNT(*) FROM assignment_submissions sub
        JOIN assignments a ON a.id = sub.assignment_id
        WHERE sub.student_id = ? AND (a.class_id IS NULL OR a.class_id = ?)""", (student_id, class_id))
    submitted = c.fetchone()[0]

    pending_assignments = max(0, total_assignments - submitted)

    c.execute("""SELECT COUNT(*) FROM lab_submissions sub JOIN lab_experiments e ON e.id=sub.experiment_id
        WHERE sub.student_id = ? AND sub.status = 'Completed' AND (e.class_id IS NULL OR e.class_id = ?)""",
        (student_id, class_id))
    completed_labs = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM lab_experiments WHERE class_id IS NULL OR class_id = ?", (class_id,))
    total_labs = c.fetchone()[0]

    lab_pct = round((completed_labs / total_labs * 100), 0) if total_labs else 0

    c.execute("""SELECT AVG(a.total_mark) / 3.0 FROM academics a
        JOIN (SELECT DISTINCT class_id, subject_id FROM teaching_assignments) ta
            ON ta.subject_id = a.subject_id AND ta.class_id = ?
        WHERE a.student_id = ?""", (class_id, student_id))
    academic_average = c.fetchone()[0]

    conn.close()
    return {
        "attendance_pct": att_pct,
        "attendance_records": total_recs,
        "pending_assignments": pending_assignments,
        "completed_labs": completed_labs,
        "total_labs": total_labs,
        "lab_pct": int(lab_pct),
        "academic_average": round(academic_average, 1) if academic_average is not None else None,
    }
