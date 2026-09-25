import sqlite3
import hashlib
import hmac
import secrets
from contextlib import closing
from datetime import date
from pathlib import Path


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "edupilot.db"
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
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_or_create_app_secret(name: str) -> str:
    conn = get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM app_settings WHERE name = ?", (name,)).fetchone()
    if row:
        conn.close()
        return row[0]
    value = secrets.token_hex(32)
    conn.execute("INSERT INTO app_settings (name, value) VALUES (?, ?)", (name, value))
    conn.commit()
    conn.close()
    return value


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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_exam_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            solution_code TEXT NOT NULL DEFAULT '',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at INTEGER,
            submitted_at TEXT,
            UNIQUE(exam_id, student_id),
            FOREIGN KEY(exam_id) REFERENCES lab_exams(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
    """)
    for column, declaration in (("started_at", "TEXT"), ("expires_at", "INTEGER")):
        try:
            cursor.execute(f"ALTER TABLE lab_exam_submissions ADD COLUMN {column} {declaration}")
        except sqlite3.OperationalError:
            pass
    cursor.execute("UPDATE lab_exam_submissions SET started_at = COALESCE(started_at, submitted_at, CURRENT_TIMESTAMP)")

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

    try:
        cursor.execute(
            "ALTER TABLE attendance_records ADD COLUMN verification_method TEXT NOT NULL DEFAULT 'manual'"
        )
    except sqlite3.OperationalError:
        pass

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
    # DEFAULT FACULTY
    # --------------------------------------------------------

    cursor.execute("SELECT id FROM users WHERE username = ?", ("faculty",))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)",
            ("faculty", hash_password("faculty123"), "faculty", "Dr. Faculty"),
        )

    # --------------------------------------------------------
    # DEMO STUDENTS
    # --------------------------------------------------------

    demo_students = [
        (
            "student",
            "student123",
            "Arun Kumar",
            "23CSE001"
        ),
        (
            "student2",
            "student123",
            "Bala Kumar",
            "23CSE002"
        ),
        (
            "student3",
            "student123",
            "Dinesh Raj",
            "23CSE003"
        ),
        (
            "student4",
            "student123",
            "Karthik S",
            "23CSE004"
        ),
        (
            "student5",
            "student123",
            "Ravi Kumar",
            "23CSE005"
        )
    ]

    for username, password, name, roll_number in demo_students:
        cursor.execute("""
            SELECT id
            FROM users
            WHERE username = ?
        """, (username,))

        user = cursor.fetchone()
        if user is None:
            cursor.execute(
                "INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)",
                (username, hash_password(password), "student", name),
            )
            user_id = cursor.lastrowid
        else:
            user_id = user[0]

        cursor.execute("""
            INSERT OR IGNORE INTO students
            (user_id, roll_number, name, department, year, section)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, roll_number, name, "CSE", 3, "C"))

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

    # Add face_encoding and qr_token columns to students table if not existing
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN face_encoding TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE students ADD COLUMN qr_token TEXT")
    except sqlite3.OperationalError:
        pass

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
    try:
        cursor.execute("ALTER TABLE assignment_submissions ADD COLUMN graded_at TEXT")
    except sqlite3.OperationalError:
        pass

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
        try:
            cursor.execute(f"ALTER TABLE question_banks ADD COLUMN {column} {declaration}")
        except sqlite3.OperationalError:
            pass

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
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS voice_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_voice_notes_owner_updated ON voice_notes(user_id, updated_at DESC)")

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

    # Populate Initial Sample Data for Timetables, Experiments, FAQs, Questions, Announcements
    cursor.execute("SELECT COUNT(*) FROM timetables")
    if cursor.fetchone()[0] == 0:
        sample_timetables = [
            (1, "Monday", "09:00", "10:00", "Lab 1", 1),
            (2, "Monday", "10:15", "11:15", "Lab 2", 1),
            (3, "Tuesday", "11:30", "12:30", "LH 102", 1),
            (4, "Wednesday", "14:00", "16:00", "Python Lab", 1),
        ]
        cursor.executemany("INSERT INTO timetables (subject_id, day_of_week, start_time, end_time, room, faculty_id) VALUES (?, ?, ?, ?, ?, ?)", sample_timetables)

    cursor.execute("SELECT COUNT(*) FROM lab_experiments")
    if cursor.fetchone()[0] == 0:
        sample_exps = [
            (4, 1, "Variables and Data Types", "Write a Python script to calculate area of basic geometric shapes.", "docs/manuals/python_exp1.pdf"),
            (4, 2, "Functions and Recursion", "Implement recursive fibonacci and factorial in Python.", "docs/manuals/python_exp2.pdf"),
            (1, 1, "Binary Search Tree Implementation", "Implement insertion, deletion, and traversal in a BST in C/C++.", "docs/manuals/ds_exp1.pdf"),
            (2, 1, "SQL Queries and Joins", "Execute DDL/DML queries and perform inner, left, and right join operations.", "docs/manuals/dbms_exp1.pdf"),
        ]
        cursor.executemany("INSERT INTO lab_experiments (subject_id, exp_number, title, description, manual_path) VALUES (?, ?, ?, ?, ?)", sample_exps)

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

    cursor.execute("SELECT COUNT(*) FROM assignments")
    if cursor.fetchone()[0] == 0:
        sample_assignments = [
            (4, "Python List Comprehensions & Lambdas", "Implement 5 matrix operations using list comprehensions and lambda functions.", "2026-08-20"),
            (2, "ER Diagram & Schema Design", "Design an ER diagram for a Hospital Management System and convert it to 3NF relations.", "2026-08-25"),
        ]
        cursor.executemany("INSERT INTO assignments (subject_id, title, description, due_date) VALUES (?, ?, ?, ?)", sample_assignments)

    cursor.execute("SELECT COUNT(*) FROM announcements")
    if cursor.fetchone()[0] == 0:
        sample_announcements = [
            (1, "Lab Exam Scheduled for Next Week", "The practical examination for DBMS Lab (CS302) is scheduled for Friday at 10:00 AM.", "All"),
            (1, "Submission Deadline Extended", "Assignment 1 submission deadline for Python Programming is extended to August 20th.", "Students")
        ]
        cursor.executemany("INSERT INTO announcements (faculty_id, title, content, target_group) VALUES (?, ?, ?, ?)", sample_announcements)

    cursor.execute("SELECT COUNT(*) FROM lab_exams")
    if cursor.fetchone()[0] == 0:
        sample_exams = [
            (4, "Python Practical Exam 1", "Question 1: Write a Python program to parse a CSV file, process student grades, and generate a summary report.\nQuestion 2: Create a GUI using PySide6 to display student records.", 60, 1),
            (2, "DBMS Practical Exam 1", "Question 1: Write SQL queries to find top 3 students by GPA.\nQuestion 2: Create a stored procedure to update attendance percentage.", 45, 0)
        ]
        cursor.executemany("INSERT INTO lab_exams (subject_id, title, question_paper_text, duration_minutes, is_active) VALUES (?, ?, ?, ?, ?)", sample_exams)

    # Keep legacy installations with multiple seeded active exams consistent with the single-active-exam workflow.
    cursor.execute("UPDATE lab_exams SET is_active = 0 WHERE is_active = 1 AND id <> (SELECT MAX(id) FROM lab_exams WHERE is_active = 1)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lab_exams_single_active ON lab_exams(is_active) WHERE is_active = 1")

    connection.commit()
    connection.close()


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

def get_students(section: str | None = None):

    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT
            id,
            roll_number,
            name,
            department,
            year,
            section
        FROM students
    """
    if section:
        cursor.execute(query + " WHERE section = ? ORDER BY roll_number", (section,))
    else:
        cursor.execute(query + " ORDER BY roll_number")

    students = cursor.fetchall()

    connection.close()

    return students


# ============================================================
# GET SUBJECTS
# ============================================================

def get_subjects():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            code,
            name
        FROM subjects
        ORDER BY code
    """)

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
):

    connection = get_connection()
    cursor = connection.cursor()

    if not records:
        raise ValueError("Attendance cannot be saved without student records.")
    cursor.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    faculty = cursor.fetchone()
    if not faculty or faculty[0] != "faculty":
        connection.close()
        raise PermissionError("Only a faculty account can save attendance.")

    # --------------------------------------------------------
    # Create or get attendance session
    # --------------------------------------------------------

    cursor.execute("""
        INSERT OR IGNORE INTO attendance_sessions
        (
            subject_id,
            faculty_id,
            class_date,
            section
        )
        VALUES (?, ?, ?, ?)
    """, (
        subject_id,
        faculty_id,
        attendance_date,
        section
    ))

    cursor.execute("""
        SELECT id
        FROM attendance_sessions
        WHERE subject_id = ?
        AND class_date = ?
        AND section = ?
    """, (
        subject_id,
        attendance_date,
        section
    ))

    session = cursor.fetchone()

    if session is None:
        connection.close()
        raise Exception("Unable to create attendance session.")

    session_id = session[0]

    # --------------------------------------------------------
    # Save every student's attendance
    # --------------------------------------------------------

    for student_id, value in records.items():
        if isinstance(value, (tuple, list)):
            status, method = value
        else:
            status, method = value, verification_method
        if status not in ("Present", "Absent"):
            connection.rollback()
            connection.close()
            raise ValueError(f"Invalid attendance status for student {student_id}.")
        if method not in ("manual", "voice", "qr", "face"):
            connection.rollback()
            connection.close()
            raise ValueError(f"Invalid attendance verification method: {method}.")

        cursor.execute("""
            INSERT INTO attendance_records
            (
                session_id,
                student_id,
                status,
                verification_method
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(session_id, student_id)
            DO UPDATE SET
                status = excluded.status,
                verification_method = excluded.verification_method,
                marked_at = CURRENT_TIMESTAMP
        """, (
            session_id,
            student_id,
            status,
            method
        ))

    _audit(cursor, faculty_id, "attendance.saved", f"session={session_id}; students={len(records)}")
    connection.commit()
    connection.close()


def get_attendance_session_records(subject_id: int, attendance_date: str, section: str = "C") -> dict:
    conn = get_connection()
    rows = conn.execute("""
        SELECT ar.student_id, ar.status, ar.verification_method
        FROM attendance_records ar
        JOIN attendance_sessions s ON s.id = ar.session_id
        WHERE s.subject_id = ? AND s.class_date = ? AND s.section = ?
    """, (subject_id, attendance_date, section)).fetchall()
    conn.close()
    return {student_id: (status, method) for student_id, status, method in rows}


def mark_student_attendance_from_qr(user_id: int, subject_id: int, attendance_date: str,
                                   faculty_id: int, section: str) -> None:
    if attendance_date != date.today().isoformat():
        raise ValueError("This attendance code is not for today.")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT st.id, st.section, u.role
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
    if student[1] != section:
        conn.close()
        raise PermissionError("This attendance code is for a different class section.")
    if not faculty or faculty[0] != "faculty" or not subject:
        conn.close()
        raise ValueError("The attendance code refers to an invalid class session.")
    cursor.execute("""
        INSERT OR IGNORE INTO attendance_sessions (subject_id, faculty_id, class_date, section)
        VALUES (?, ?, ?, ?)
    """, (subject_id, faculty_id, attendance_date, student[1]))
    cursor.execute("""
        SELECT id FROM attendance_sessions
        WHERE subject_id = ? AND class_date = ? AND section = ?
    """, (subject_id, attendance_date, student[1]))
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
            section
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
        WHERE st.user_id = ?
        ORDER BY s.code
    """, (user_id,)).fetchall()
    conn.close()
    return rows


def get_all_academic_records():
    conn = get_connection()
    rows = conn.execute("""
        SELECT st.id, st.roll_number, st.name, s.id, s.code, s.name,
               a.internal_mark, a.assignment_mark, a.lab_mark, a.total_mark
        FROM students st
        CROSS JOIN subjects s
        LEFT JOIN academics a ON a.student_id = st.id AND a.subject_id = s.id
        ORDER BY st.roll_number, s.code
    """).fetchall()
    conn.close()
    return rows


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

            COUNT(ar.id) AS total_classes,

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

        CROSS JOIN subjects s

        LEFT JOIN attendance_sessions ats
            ON ats.subject_id = s.id
            AND ats.section = st.section

        LEFT JOIN attendance_records ar
            ON ar.session_id = ats.id
            AND ar.student_id = st.id

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
            ar.status

        FROM students st

        INNER JOIN attendance_records ar
            ON ar.student_id = st.id

        INNER JOIN attendance_sessions ats
            ON ats.id = ar.session_id

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

def get_timetables():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT t.id, s.code, s.name, t.day_of_week, t.start_time, t.end_time, t.room, t.faculty_id
        FROM timetables t
        JOIN subjects s ON s.id = t.subject_id
        ORDER BY t.day_of_week, t.start_time
    """)
    rows = c.fetchall()
    conn.close()
    return rows


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
                        room: str, faculty_id: int) -> int:
    _validate_timetable_values(day_of_week, start_time, end_time, room)
    conn = get_connection()
    c = conn.cursor()
    try:
        role = c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can manage the timetable.")
        if not c.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
            raise ValueError("Choose a valid subject.")
        overlap = c.execute("""SELECT 1 FROM timetables
            WHERE day_of_week = ? AND start_time < ? AND end_time > ?
              AND (faculty_id = ? OR room = ? COLLATE NOCASE) LIMIT 1""",
            (day_of_week, end_time, start_time, faculty_id, room.strip())).fetchone()
        if overlap:
            raise ValueError("This time conflicts with another class for the faculty member or room.")
        c.execute("""INSERT INTO timetables (subject_id, day_of_week, start_time, end_time, room, faculty_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (subject_id, day_of_week, start_time, end_time, room.strip(), faculty_id))
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
                           end_time: str, room: str, faculty_id: int) -> None:
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
        overlap = c.execute("""SELECT 1 FROM timetables
            WHERE id <> ? AND day_of_week = ? AND start_time < ? AND end_time > ?
              AND (faculty_id = ? OR room = ? COLLATE NOCASE) LIMIT 1""",
            (entry_id, day_of_week, end_time, start_time, faculty_id, room.strip())).fetchone()
        if overlap:
            raise ValueError("This time conflicts with another class for the faculty member or room.")
        c.execute("""UPDATE timetables SET subject_id = ?, day_of_week = ?, start_time = ?,
            end_time = ?, room = ? WHERE id = ?""",
            (subject_id, day_of_week, start_time, end_time, room.strip(), entry_id))
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


def get_assignments():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT a.id, s.code, s.name, a.title, a.description, a.due_date, a.max_marks
        FROM assignments a
        JOIN subjects s ON s.id = a.subject_id
        ORDER BY a.due_date
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def add_assignment(subject_id, title, description, due_date, faculty_id=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can publish assignments.")
    c.execute("INSERT INTO assignments (subject_id, title, description, due_date) VALUES (?, ?, ?, ?)",
              (subject_id, title, description, due_date))
    _audit(c, faculty_id, "assignment.created", f"assignment={c.lastrowid}; title={title}")
    conn.commit()
    conn.close()


def get_notes():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT n.id, s.code, s.name, n.unit_number, n.title, n.file_path, n.created_at
        FROM notes n
        JOIN subjects s ON s.id = n.subject_id
        ORDER BY s.code, n.unit_number
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def add_note(subject_id, title, file_path, unit_number=1, uploaded_by=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (uploaded_by,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can upload course notes.")
    c.execute("INSERT INTO notes (subject_id, title, file_path, unit_number, uploaded_by) VALUES (?, ?, ?, ?, ?)",
              (subject_id, title, file_path, unit_number, uploaded_by))
    _audit(c, uploaded_by, "note.uploaded", f"title={title}")
    conn.commit()
    conn.close()


def get_question_banks():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT q.id, s.code, s.name, q.unit_number, q.question, q.answer_key,
               q.difficulty, q.marks, q.source_kind, q.exam_year
        FROM question_banks q
        JOIN subjects s ON s.id = q.subject_id
        ORDER BY s.code, q.unit_number
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def get_lab_experiments():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT e.id, s.code, s.name, e.exp_number, e.title, e.description, e.manual_path
        FROM lab_experiments e
        JOIN subjects s ON s.id = e.subject_id
        ORDER BY s.code, e.exp_number
    """)
    rows = c.fetchall()
    conn.close()
    return rows


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


def get_announcements(role: str | None = None):
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT a.id, u.name, a.title, a.content, a.target_group, a.created_at
        FROM announcements a
        JOIN users u ON u.id = a.faculty_id
    """
    if role == "student":
        query += " WHERE a.target_group IN ('All', 'Students')"
    query += " ORDER BY a.created_at DESC"
    c.execute(query)
    rows = c.fetchall()
    conn.close()
    return rows


def add_announcement(faculty_id, title, content, target_group="All"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can publish announcements.")
    c.execute("INSERT INTO announcements (faculty_id, title, content, target_group) VALUES (?, ?, ?, ?)",
              (faculty_id, title, content, target_group))
    _audit(c, faculty_id, "announcement.created", f"title={title}; audience={target_group}")
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
                             subject_id: int | None = None, section: str | None = None):
    if start_date:
        date.fromisoformat(start_date)
    if end_date:
        date.fromisoformat(end_date)
    if start_date and end_date and start_date > end_date:
        raise ValueError("The report start date must be on or before the end date.")
    conn = get_connection()
    c = conn.cursor()
    session_filters, params = [], []
    for clause, value in (("sess.class_date >= ?", start_date), ("sess.class_date <= ?", end_date),
                          ("sess.subject_id = ?", subject_id), ("sess.section = ?", section)):
        if value is not None:
            session_filters.append(clause)
            params.append(value)
    scoped_sessions = ""
    if session_filters:
        scoped_sessions = " AND EXISTS (SELECT 1 FROM attendance_sessions sess WHERE sess.id = ar.session_id AND " + " AND ".join(session_filters) + ")"
    c.execute("""
        SELECT
            st.roll_number,
            st.name,
            COUNT(ar.id) as total_sessions,
            SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) as present_count,
            ROUND(CAST(SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) AS FLOAT) / MAX(1, COUNT(ar.id)) * 100, 1) as percentage
        FROM students st
        LEFT JOIN attendance_records ar ON ar.student_id = st.id
    """ + scoped_sessions + """
        GROUP BY st.id, st.roll_number, st.name
        ORDER BY percentage ASC
    """, params)
    rows = c.fetchall()
    conn.close()
    return rows


def get_voice_notes(user_id: int) -> list[tuple]:
    """Return the current user's private notes, most recently updated first."""
    with closing(get_connection()) as conn:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not role:
            raise PermissionError("Sign in to view your private notes.")
        return conn.execute(
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
    with closing(get_connection()) as conn:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not role:
            raise PermissionError("Sign in to save private notes.")
        if note_id is None:
            cursor = conn.execute(
                "INSERT INTO voice_notes (user_id, title, content) VALUES (?, ?, ?)",
                (user_id, title, content),
            )
            _audit(conn.cursor(), user_id, "voice_note.created", f"note={cursor.lastrowid}; title={title}")
            conn.commit()
            return cursor.lastrowid
        cursor = conn.execute(
            "UPDATE voice_notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ?",
            (title, content, note_id, user_id),
        )
        if cursor.rowcount != 1:
            raise PermissionError("That note does not belong to your account or no longer exists.")
        _audit(conn.cursor(), user_id, "voice_note.updated", f"note={note_id}; title={title}")
        conn.commit()
        return note_id


def delete_voice_note(user_id: int, note_id: int) -> None:
    """Delete one of the current user's private notes and log the action."""
    with closing(get_connection()) as conn:
        cursor = conn.execute("DELETE FROM voice_notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        if cursor.rowcount != 1:
            raise PermissionError("That note does not belong to your account or no longer exists.")
        _audit(conn.cursor(), user_id, "voice_note.deleted", f"note={note_id}")
        conn.commit()
    return rows


def record_assistant_query_event(category: str = "learning") -> None:
    if category not in ("learning", "schedule", "exam"):
        raise ValueError("Unknown assistant analytics category.")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO assistant_query_events(category) VALUES (?)", (category,))
        conn.execute("DELETE FROM assistant_query_events WHERE created_at < datetime('now', '-90 days')")
        conn.commit()
    finally:
        conn.close()


def get_classroom_activity_stats() -> dict:
    conn = get_connection()
    try:
        return {
            "learning_queries_today": conn.execute(
                "SELECT COUNT(*) FROM assistant_query_events WHERE category = 'learning' AND date(created_at, 'localtime') = date('now', 'localtime')"
            ).fetchone()[0],
            "schedule_queries_today": conn.execute(
                "SELECT COUNT(*) FROM assistant_query_events WHERE category = 'schedule' AND date(created_at, 'localtime') = date('now', 'localtime')"
            ).fetchone()[0],
            "exam_queries_today": conn.execute(
                "SELECT COUNT(*) FROM assistant_query_events WHERE category = 'exam' AND date(created_at, 'localtime') = date('now', 'localtime')"
            ).fetchone()[0],
            "lab_submissions_today": conn.execute(
                "SELECT COUNT(*) FROM lab_submissions WHERE date(completed_at, 'localtime') = date('now', 'localtime')"
            ).fetchone()[0],
            "attendance_sessions_today": conn.execute(
                "SELECT COUNT(*) FROM attendance_sessions WHERE class_date = date('now', 'localtime')"
            ).fetchone()[0],
            "assignment_submissions_today": conn.execute(
                "SELECT COUNT(*) FROM assignment_submissions WHERE date(submitted_at, 'localtime') = date('now', 'localtime')"
            ).fetchone()[0],
        }
    finally:
        conn.close()


def get_assignment_submissions(assignment_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT sub.id, st.roll_number, st.name, sub.submission_text, sub.file_path,
               sub.submitted_at, sub.marks, sub.feedback, sub.graded_at
        FROM assignment_submissions sub
        JOIN students st ON st.id = sub.student_id
        WHERE sub.assignment_id = ?
        ORDER BY sub.submitted_at DESC
    """, (assignment_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_student_lab_progress(user_id: int):
    conn = get_connection()
    try:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not role or role[0] != "student":
            raise PermissionError("A student account is required to view personal lab progress.")
        return conn.execute("""SELECT e.id, s.code, s.name, e.exp_number, e.title, e.description,
            COALESCE(sub.status, 'Not started'), COALESCE(sub.code_snippet, '')
            FROM lab_experiments e JOIN subjects s ON s.id = e.subject_id
            LEFT JOIN students st ON st.user_id = ?
            LEFT JOIN lab_submissions sub ON sub.experiment_id = e.id AND sub.student_id = st.id
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
        if not conn.execute("SELECT 1 FROM lab_experiments WHERE id = ?", (experiment_id,)).fetchone():
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
            sub.code_snippet, sub.completed_at, sub.status FROM lab_submissions sub
            JOIN students st ON st.id = sub.student_id JOIN lab_experiments e ON e.id = sub.experiment_id
            JOIN subjects s ON s.id = e.subject_id WHERE sub.status IN ('Submitted for Review','Needs Revision')
            ORDER BY sub.completed_at""").fetchall()
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


def get_lab_exam_catalog():
    conn = get_connection()
    rows = conn.execute("""SELECT e.id, s.code, s.name, e.title, e.duration_minutes, e.is_active, e.created_at
        FROM lab_exams e JOIN subjects s ON s.id = e.subject_id ORDER BY e.created_at DESC, e.id DESC""").fetchall()
    conn.close()
    return rows


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
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM students WHERE user_id = ?", (user_id,))
    st = c.fetchone()
    if not st:
        conn.close()
        return False
    student_id = st[0]

    c.execute("""
        INSERT INTO assignment_submissions (assignment_id, student_id, submission_text, file_path, marks, feedback, graded_at)
        VALUES (?, ?, ?, ?, NULL, NULL, NULL)
        ON CONFLICT(assignment_id, student_id) DO UPDATE SET
            submission_text = excluded.submission_text,
            file_path = excluded.file_path,
            submitted_at = CURRENT_TIMESTAMP,
            marks = NULL,
            feedback = NULL,
            graded_at = NULL
    """, (assignment_id, student_id, submission_text, file_path))
    _audit(c, user_id, "assignment.submitted", f"assignment={assignment_id}; student={student_id}")
    conn.commit()
    conn.close()
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
        SELECT a.max_marks FROM assignment_submissions s
        JOIN assignments a ON a.id = s.assignment_id
        WHERE s.id = ?
    """, (submission_id,))
    assignment = c.fetchone()
    if not assignment or marks < 0 or marks > assignment[0]:
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
                          source_kind: str = "Model", exam_year: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    try:
        role = c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,)).fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can add question-bank items.")
        if source_kind not in ("Model", "Previous Year"):
            raise ValueError("Question source must be Model or Previous Year.")
        if source_kind == "Previous Year" and (exam_year is None or not 2000 <= int(exam_year) <= date.today().year):
            raise ValueError("Enter a valid exam year for a previous-year question.")
        if source_kind == "Model":
            exam_year = None
        c.execute("""INSERT INTO question_banks
            (subject_id, unit_number, question, answer_key, difficulty, marks, source_kind, exam_year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (subject_id, unit_number, question, answer_key, difficulty, marks, source_kind, exam_year))
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

def add_student(username: str, roll_number: str, name: str, department: str = "CSE", year: int = 3, section: str = "C", password: str = "student123", faculty_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
        role = c.fetchone()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can create student accounts.")
        if not password:
            raise ValueError("A temporary password is required.")
        c.execute("INSERT INTO users (username, password, role, name) VALUES (?, ?, 'student', ?)",
                  (username, hash_password(password), name))
        user_id = c.lastrowid
        c.execute("""
            INSERT INTO students (user_id, roll_number, name, department, year, section)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, roll_number, name, department, year, section))
        student_id = c.lastrowid
        _audit(c, faculty_id, "student.created", f"student={student_id}; username={username}")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e


def update_student(student_id: int, roll_number: str, name: str, department: str, year: int, section: str, faculty_id: int | None = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (faculty_id,))
    role = c.fetchone()
    if not role or role[0] != "faculty":
        conn.close()
        raise PermissionError("Only faculty can update student records.")
    c.execute("""
        UPDATE students
        SET roll_number = ?, name = ?, department = ?, year = ?, section = ?
        WHERE id = ?
    """, (roll_number, name, department, year, section, student_id))
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

def get_dashboard_stats_faculty():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM students")
    total_students = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(ar.id), SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END)
        FROM attendance_records ar
    """)
    row = c.fetchone()
    total_recs, present_recs = row[0] or 0, row[1] or 0
    att_pct = round((present_recs / total_recs * 100), 1) if total_recs > 0 else None

    c.execute("SELECT COUNT(*) FROM assignments")
    total_assignments = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM announcements")
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

    c.execute("SELECT id FROM students WHERE user_id = ?", (user_id,))
    st = c.fetchone()
    if not st:
        conn.close()
        return {
            "attendance_pct": None, "attendance_records": 0,
            "pending_assignments": 0, "completed_labs": 0,
            "total_labs": 0, "lab_pct": 0, "academic_average": None,
        }
    student_id = st[0]

    c.execute("""
        SELECT COUNT(ar.id), SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END)
        FROM attendance_records ar
        WHERE ar.student_id = ?
    """, (student_id,))
    row = c.fetchone()
    total_recs, present_recs = row[0] or 0, row[1] or 0
    att_pct = round((present_recs / total_recs * 100), 1) if total_recs > 0 else None

    c.execute("SELECT COUNT(*) FROM assignments")
    total_assignments = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM assignment_submissions WHERE student_id = ?", (student_id,))
    submitted = c.fetchone()[0]

    pending_assignments = max(0, total_assignments - submitted)

    c.execute("SELECT COUNT(*) FROM lab_submissions WHERE student_id = ? AND status = 'Completed'", (student_id,))
    completed_labs = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM lab_experiments")
    total_labs = c.fetchone()[0]

    lab_pct = round((completed_labs / total_labs * 100), 0) if total_labs else 0

    c.execute("SELECT AVG(total_mark) / 3.0 FROM academics WHERE student_id = ?", (student_id,))
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
