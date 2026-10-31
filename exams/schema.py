"""Portable relational schema for the online examination module."""


def ensure_exam_schema(cursor) -> None:
    """Create additive exam tables on SQLite or PostgreSQL connections."""
    statements = (
        """
        CREATE TABLE IF NOT EXISTS online_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id BIGINT NOT NULL,
            subject_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            exam_type TEXT NOT NULL DEFAULT 'Mixed',
            duration_minutes INTEGER NOT NULL,
            starts_at TEXT,
            ends_at TEXT,
            total_marks REAL NOT NULL DEFAULT 0,
            passing_marks REAL NOT NULL DEFAULT 0,
            negative_marking INTEGER NOT NULL DEFAULT 0,
            max_violations INTEGER NOT NULL DEFAULT 3,
            violation_action TEXT NOT NULL DEFAULT 'faculty_approval',
            auto_submit INTEGER NOT NULL DEFAULT 1,
            randomize_questions INTEGER NOT NULL DEFAULT 0,
            randomize_options INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            class_id BIGINT,
            FOREIGN KEY(faculty_id) REFERENCES users(id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id),
            CHECK(exam_type IN ('MCQ','Multiple Select','True/False','Fill in the Blank',
                'Short Answer','Descriptive','Programming','Mixed')),
            CHECK(status IN ('draft','published','closed','deleted')),
            CHECK(duration_minutes BETWEEN 1 AND 1440),
            CHECK(total_marks >= 0 AND passing_marks >= 0),
            CHECK(max_violations BETWEEN 1 AND 20)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id BIGINT NOT NULL,
            subject_id BIGINT NOT NULL,
            question_type TEXT NOT NULL,
            prompt TEXT NOT NULL,
            topic TEXT,
            difficulty TEXT NOT NULL DEFAULT 'Medium',
            marks REAL NOT NULL DEFAULT 1,
            negative_marks REAL NOT NULL DEFAULT 0,
            correct_answer TEXT,
            accepted_answers TEXT,
            matching_mode TEXT NOT NULL DEFAULT 'case_insensitive',
            auto_grade INTEGER NOT NULL DEFAULT 0,
            explanation TEXT,
            programming_language TEXT,
            starter_code TEXT,
            input_format TEXT,
            output_format TEXT,
            constraints_text TEXT,
            sample_cases TEXT,
            time_limit_seconds INTEGER NOT NULL DEFAULT 5,
            memory_limit_mb INTEGER NOT NULL DEFAULT 256,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(faculty_id) REFERENCES users(id),
            FOREIGN KEY(subject_id) REFERENCES subjects(id),
            CHECK(question_type IN ('mcq','multiple_select','true_false','fill_blank',
                'short_answer','descriptive','programming')),
            CHECK(difficulty IN ('Easy','Medium','Hard')),
            CHECK(marks > 0 AND negative_marks >= 0 AND negative_marks <= marks),
            CHECK(matching_mode IN ('exact','case_insensitive','whitespace_insensitive')),
            CHECK(time_limit_seconds BETWEEN 1 AND 60),
            CHECK(memory_limit_mb BETWEEN 32 AND 1024)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_question_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id BIGINT NOT NULL,
            option_order INTEGER NOT NULL,
            option_text TEXT NOT NULL,
            is_correct INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(question_id) REFERENCES online_questions(id) ON DELETE CASCADE,
            UNIQUE(question_id, option_order)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_coding_test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id BIGINT NOT NULL,
            case_order INTEGER NOT NULL,
            input_text TEXT NOT NULL DEFAULT '',
            expected_output TEXT NOT NULL,
            is_hidden INTEGER NOT NULL DEFAULT 1,
            marks REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(question_id) REFERENCES online_questions(id) ON DELETE CASCADE,
            UNIQUE(question_id, case_order),
            CHECK(marks >= 0)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_exam_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id BIGINT NOT NULL,
            question_id BIGINT NOT NULL,
            question_order INTEGER NOT NULL,
            marks_override REAL,
            FOREIGN KEY(exam_id) REFERENCES online_exams(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES online_questions(id),
            UNIQUE(exam_id, question_id),
            UNIQUE(exam_id, question_order),
            CHECK(marks_override IS NULL OR marks_override > 0)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id BIGINT NOT NULL,
            student_id BIGINT NOT NULL,
            started_at INTEGER NOT NULL,
            ends_at INTEGER NOT NULL,
            submitted_at TEXT,
            status TEXT NOT NULL DEFAULT 'in_progress',
            violation_count INTEGER NOT NULL DEFAULT 0,
            paused_at TEXT,
            last_saved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(exam_id) REFERENCES online_exams(id),
            FOREIGN KEY(student_id) REFERENCES students(id),
            UNIQUE(exam_id, student_id),
            CHECK(status IN ('in_progress','paused','submitted','auto_submitted','ended')),
            CHECK(violation_count >= 0)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_student_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id BIGINT NOT NULL,
            question_id BIGINT NOT NULL,
            answer_json TEXT,
            marks_awarded REAL,
            evaluation_status TEXT NOT NULL DEFAULT 'ungraded',
            feedback TEXT,
            saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(attempt_id) REFERENCES online_exam_attempts(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES online_questions(id),
            UNIQUE(attempt_id, question_id),
            CHECK(evaluation_status IN ('ungraded','auto_graded','pending_review','pending_evaluation','graded'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_attempt_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id BIGINT NOT NULL,
            question_id BIGINT NOT NULL,
            question_order INTEGER NOT NULL,
            option_order_json TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(attempt_id) REFERENCES online_exam_attempts(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES online_questions(id),
            UNIQUE(attempt_id, question_id),
            UNIQUE(attempt_id, question_order)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_code_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id BIGINT NOT NULL,
            question_id BIGINT NOT NULL,
            programming_language TEXT NOT NULL,
            source_code TEXT NOT NULL,
            run_output TEXT,
            passed_cases INTEGER,
            total_cases INTEGER,
            marks_awarded REAL,
            status TEXT NOT NULL DEFAULT 'submitted',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(attempt_id) REFERENCES online_exam_attempts(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES online_questions(id),
            CHECK(status IN ('submitted','running','evaluated','failed'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_exam_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id BIGINT NOT NULL,
            event_type TEXT NOT NULL,
            event_at TEXT DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY(attempt_id) REFERENCES online_exam_attempts(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_exam_faculty_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id BIGINT NOT NULL,
            faculty_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            reset_violations INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(attempt_id) REFERENCES online_exam_attempts(id) ON DELETE CASCADE,
            FOREIGN KEY(faculty_id) REFERENCES users(id),
            CHECK(action IN ('allow_continue','keep_paused','end_exam'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS online_exam_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id BIGINT NOT NULL UNIQUE,
            marks_awarded REAL NOT NULL DEFAULT 0,
            total_marks REAL NOT NULL DEFAULT 0,
            percentage REAL NOT NULL DEFAULT 0,
            outcome TEXT NOT NULL DEFAULT 'Pending review',
            result_json TEXT,
            evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(attempt_id) REFERENCES online_exam_attempts(id) ON DELETE CASCADE,
            CHECK(outcome IN ('Pass','Fail','Pending review'))
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_online_exams_schedule ON online_exams(status, starts_at, ends_at)",
        "CREATE INDEX IF NOT EXISTS idx_online_questions_subject ON online_questions(subject_id, question_type, difficulty)",
        "CREATE INDEX IF NOT EXISTS idx_online_attempts_student ON online_exam_attempts(student_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_online_attempts_exam ON online_exam_attempts(exam_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_online_violations_attempt ON online_exam_violations(attempt_id, event_at)",
    )
    for statement in statements:
        cursor.execute(statement)
