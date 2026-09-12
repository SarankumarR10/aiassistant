import sqlite3
from pathlib import Path


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "edupilot.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


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

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (
            username,
            password,
            role,
            name
        )
        VALUES (?, ?, ?, ?)
    """, (
        "faculty",
        "faculty123",
        "faculty",
        "Dr. Faculty"
    ))

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
            INSERT OR IGNORE INTO users
            (
                username,
                password,
                role,
                name
            )
            VALUES (?, ?, ?, ?)
        """, (
            username,
            password,
            "student",
            name
        ))

        cursor.execute("""
            SELECT id
            FROM users
            WHERE username = ?
        """, (username,))

        user = cursor.fetchone()

        if user:

            user_id = user[0]

            cursor.execute("""
                INSERT OR IGNORE INTO students
                (
                    user_id,
                    roll_number,
                    name,
                    department,
                    year,
                    section
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                roll_number,
                name,
                "CSE",
                3,
                "C"
            ))

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
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

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
            (2, "DBMS Practical Exam 1", "Question 1: Write SQL queries to find top 3 students by GPA.\nQuestion 2: Create a stored procedure to update attendance percentage.", 45, 1)
        ]
        cursor.executemany("INSERT INTO lab_exams (subject_id, title, question_paper_text, duration_minutes, is_active) VALUES (?, ?, ?, ?, ?)", sample_exams)

    connection.commit()
    connection.close()


# ============================================================
# LOGIN
# ============================================================

def authenticate_user(username, password):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            username,
            role,
            name
        FROM users
        WHERE username = ?
        AND password = ?
    """, (
        username,
        password
    ))

    user = cursor.fetchone()

    connection.close()

    return user


# ============================================================
# GET STUDENTS
# ============================================================

def get_students():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            roll_number,
            name,
            department,
            year,
            section
        FROM students
        ORDER BY roll_number
    """)

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
    section="C"
):

    connection = get_connection()
    cursor = connection.cursor()

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

    for student_id, status in records.items():

        cursor.execute("""
            INSERT INTO attendance_records
            (
                session_id,
                student_id,
                status
            )
            VALUES (?, ?, ?)

            ON CONFLICT(session_id, student_id)
            DO UPDATE SET
                status = excluded.status,
                marked_at = CURRENT_TIMESTAMP
        """, (
            session_id,
            student_id,
            status
        ))

    connection.commit()
    connection.close()


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
        SELECT t.id, s.code, s.name, t.day_of_week, t.start_time, t.end_time, t.room
        FROM timetables t
        JOIN subjects s ON s.id = t.subject_id
        ORDER BY t.day_of_week, t.start_time
    """)
    rows = c.fetchall()
    conn.close()
    return rows


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


def add_assignment(subject_id, title, description, due_date):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO assignments (subject_id, title, description, due_date) VALUES (?, ?, ?, ?)",
              (subject_id, title, description, due_date))
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


def add_note(subject_id, title, file_path, unit_number=1, uploaded_by=1):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO notes (subject_id, title, file_path, unit_number, uploaded_by) VALUES (?, ?, ?, ?, ?)",
              (subject_id, title, file_path, unit_number, uploaded_by))
    conn.commit()
    conn.close()


def get_question_banks():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT q.id, s.code, s.name, q.unit_number, q.question, q.answer_key, q.difficulty, q.marks
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
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def get_announcements():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT a.id, u.name, a.title, a.content, a.target_group, a.created_at
        FROM announcements a
        JOIN users u ON u.id = a.faculty_id
        ORDER BY a.created_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def add_announcement(faculty_id, title, content, target_group="All"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO announcements (faculty_id, title, content, target_group) VALUES (?, ?, ?, ?)",
              (faculty_id, title, content, target_group))
    conn.commit()
    conn.close()


def get_reminders(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, title, reminder_type, due_date, is_completed
        FROM reminders
        WHERE user_id = ? OR user_id = 1
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


def get_attendance_analytics():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT 
            st.roll_number,
            st.name,
            COUNT(ar.id) as total_sessions,
            SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) as present_count,
            ROUND(CAST(SUM(CASE WHEN ar.status = 'Present' THEN 1 ELSE 0 END) AS FLOAT) / MAX(1, COUNT(ar.id)) * 100, 1) as percentage
        FROM students st
        LEFT JOIN attendance_records ar ON ar.student_id = st.id
        GROUP BY st.id, st.roll_number, st.name
        ORDER BY percentage ASC
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def get_assignment_submissions(assignment_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT sub.id, st.roll_number, st.name, sub.submission_text, sub.file_path, sub.submitted_at, sub.marks, sub.feedback
        FROM assignment_submissions sub
        JOIN students st ON st.id = sub.student_id
        WHERE sub.assignment_id = ?
        ORDER BY sub.submitted_at DESC
    """, (assignment_id,))
    rows = c.fetchall()
    conn.close()
    return rows


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
        INSERT INTO assignment_submissions (assignment_id, student_id, submission_text, file_path)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(assignment_id, student_id) DO UPDATE SET
            submission_text = excluded.submission_text,
            file_path = excluded.file_path,
            submitted_at = CURRENT_TIMESTAMP
    """, (assignment_id, student_id, submission_text, file_path))
    conn.commit()
    conn.close()
    return True


def grade_submission(submission_id: int, marks: float, feedback: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE assignment_submissions
        SET marks = ?, feedback = ?
        WHERE id = ?
    """, (marks, feedback, submission_id))
    conn.commit()
    conn.close()
    return True


def add_question_bank_item(subject_id: int, unit_number: int, question: str, answer_key: str, difficulty: str = "Medium", marks: int = 5):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO question_banks (subject_id, unit_number, question, answer_key, difficulty, marks)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (subject_id, unit_number, question, answer_key, difficulty, marks))
    conn.commit()
    conn.close()
    return True


def toggle_reminder_completed(reminder_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE reminders
        SET is_completed = CASE WHEN is_completed = 1 THEN 0 ELSE 1 END
        WHERE id = ?
    """, (reminder_id,))
    conn.commit()
    conn.close()
    return True
