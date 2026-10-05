# EduPilot architecture

## Product shape

EduPilot is a local-first Windows/macOS/Linux desktop app. It has no web client or remote server, so screens call Python feature modules directly. Those modules validate the signed-in role and use parameterized SQLite operations. This keeps setup small and allows the core classroom workflows to run without a network connection.

```text
PySide6 UI
  ├─ Faculty / student dashboards
  └─ Feature widgets
       ↓
Python feature services
  ├─ Attendance and signed QR validation
  ├─ Academic, assignment, lab, notice and schedule workflows
  ├─ Local FAQ/document retrieval
  └─ Local storage service
       ↓                         ↓
SQLite records and metadata   Per-user files directory
```

## Main components

| Area | Location | Responsibility |
| --- | --- | --- |
| Application startup | `main.py` | Start Qt, initialize/migrate the local database, show a clear startup error, open login |
| Authentication | `gui/login.py`, `database/database.py` | Verify PBKDF2-SHA256 password hashes and route to role-specific workspace |
| Faculty workspace | `gui/faculty_dashboard.py` | Directory, attendance, analytics, academics, assignments, local study tools, timetable, lab and notices |
| Student workspace | `gui/student_dashboard.py` | Personal records, submissions, schedule, notices, course materials and study tools |
| Database | `database/database.py` | SQLite schema, additive migrations, role checks, data access, audit events and seed examples |
| Course retrieval | `ai/rag_engine.py` | Index approved local text/PDF material and retrieve local FAQ, notes and question-bank matches |
| File storage | `storage/local_storage.py` | Validate and copy uploads under unique local keys; resolve paths safely; record metadata and prune unreferenced uploads |
| Optional execution | `lab/code_runner.py`, `docker/Dockerfile.runner` | Run code through a restricted Docker container, when the image is installed |

## Data model

The SQLite database stores account and classroom records: `users`, `students`, `subjects`, `attendance_sessions`, `attendance_records`, `academics`, `timetables`, `assignments`, `assignment_submissions`, `notes`, `question_banks`, `documents`, `document_chunks`, `lab_experiments`, `lab_submissions`, `lab_exams`, `lab_exam_submissions`, `announcements`, `reminders`, `voice_notes`, `assistant_query_events`, `audit_log`, `app_settings`, and `stored_files`.

Foreign keys and unique constraints protect core relationships and duplicate attendance/submission records. Indexes cover common date, owner, assignment, document-chunk, and reminder queries. Existing project-folder databases migrate by SQLite backup into the user data folder; schema updates add missing columns and keep existing rows. `PRAGMA user_version` records the current schema generation.

## File storage

Binary uploads are not put into SQLite. `LocalStorageService` streams the selected file into a category folder using a random file name. It allows only configured document and submission extensions and caps uploads at 25 MB. The database records an opaque key, original name, MIME type, byte size, owner, and timestamp. UI components resolve stored keys through the service instead of trusting user-provided paths.

Use `EDUPILOT_DATA_DIR` to move the database and default files directory together, `EDUPILOT_DB_PATH` to select a SQLite file, or `EDUPILOT_FILES_DIR` to move uploaded files separately. Back up the database and file directory as a pair. Existing legacy paths continue to work on the computer where they were created; newly uploaded files are managed and portable with that pair.

The storage boundary is provider-oriented, but only local filesystem storage exists today. S3-compatible storage, signed URLs, remote file authorization, and multi-device synchronization require a future server/API deployment and are not claimed as implemented.

## Security and limits

- Passwords use salted PBKDF2-SHA256 and constant-time comparison.
- User values are passed as SQL parameters; faculty-only operations check the account role in the data layer.
- Students retrieve personal attendance, marks, reminders, and submissions using their user identity; course notes are shared through the approved course workspace.
- QR attendance tokens are signed with HMAC-SHA256 and expire after five minutes. A valid code can still be shared, so QR is not described as identity proof.
- Student uploads are extension-allowlisted and size-limited. They are stored as files and are never executed by EduPilot.
- Code execution requires Docker and applies network, filesystem, process, CPU, memory, user, and timeout restrictions. No host-shell fallback is provided.
- This app is for local desktop use. It does not provide remote sessions, server-side rate limiting, REST endpoints, CORS, cloud storage, or institution-wide multi-user synchronization.

## Checks

Run the standard-library core workflow suite with:

```text
python -m unittest discover -s tests -v
```

The suite covers repeatable schema initialization, login hashing, legacy database copy, signed QR attendance, assignment file storage, local document retrieval, and orphan cleanup. UI integration still requires installing the GUI dependencies listed in `requirements.txt` and launching with `run.bat` or `run.sh`.
