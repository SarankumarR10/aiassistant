# EduPilot architecture

## Product shape

EduPilot is a local-first PySide6 desktop app. The faculty and student screens call Python feature modules directly; there is no web client or application server in this build. The app works with SQLite alone. When PostgreSQL is configured, shared classroom records use PostgreSQL while private device data remains in SQLite.

```text
PySide6 desktop UI
  ├─ Faculty workspace
  └─ Student workspace
       ↓
Python feature modules
  ├─ Login, attendance, QR validation, academics, assignments
  ├─ Timetable, notices, reminders, labs, and practical exams
  ├─ Local course-document search and optional offline speech
  └─ Role checks, input validation, and report generation
       ↓
PostgreSQL (shared academic records, when configured)
SQLite (single-device records and private local data)
Local managed files (course uploads and assignment attachments)
```

## Main components

| Area | Location | Responsibility |
| --- | --- | --- |
| Startup | `main.py` | Starts Qt, initializes configured stores, reports startup errors, and opens login. |
| Authentication | `gui/login.py`, `database/database.py` | Verifies salted PBKDF2-SHA256 password hashes and selects the faculty or student workspace. |
| Faculty workspace | `gui/faculty_dashboard.py` | Student directory, attendance, analytics, academics, assignments, notes, notices, timetable, workstation, voice, exam management, and lab review. |
| Student workspace | `gui/student_dashboard.py` | Personal attendance and academics, assignments, course materials, code runner, labs, schedule, practical exams, voice tools, and private notes. |
| Data access | `database/database.py` | Creates and migrates schemas, performs parameterized queries, enforces role checks, records audit events, and seeds demo data. |
| PostgreSQL adapter | `database/postgres_compat.py` | Translates the current SQLite-shaped data-layer SQL into the subset used with PostgreSQL. It is a compatibility layer, not a replacement for a future versioned migration/service architecture. |
| Course retrieval | `ai/rag_engine.py`, `ai/tutor_engine.py` | Indexes readable local text/PDF material and returns matching FAQs, document passages, and question-bank results with source labels. Retrieval is local; no generative language model is bundled. |
| File storage | `storage/local_storage.py` | Copies allowed uploads under opaque random keys, checks size and path containment, and stores file metadata in the configured shared database. |
| Optional code execution | `lab/code_runner.py`, `docker/Dockerfile.runner` | Runs student code only in the restricted Docker image when Docker and that image are available. |
| Voice | `voice/`, `gui/speech_worker.py` | Handles typed commands and optional local Vosk microphone input. Recognized commands are shown for review, and sensitive actions require confirmation. |

## Data placement

| Store | Contents | Sharing behaviour |
| --- | --- | --- |
| PostgreSQL, when configured | Accounts, students, attendance, academics, assignments/submissions, course material metadata, question bank, notices, reminders, timetable, lab work, practical exams, audit events, and shared app settings such as the QR signing key. | Shared by clients connected to the same database. |
| SQLite | Private voice notes, local application settings/secrets, and all structured app data when PostgreSQL is not configured. | Belongs to one installation unless the user manually moves/backups the database. |
| Local files directory | Uploaded course documents and assignment attachments. The database stores opaque keys and metadata, not their binary contents. | Files stay on each computer; PostgreSQL does not synchronize them. |

With PostgreSQL configured, QR tokens use a shared HMAC secret in PostgreSQL so a faculty device can issue a code that a student device connected to that same database can validate. In SQLite-only mode, the secret remains local, which is appropriate for a single-device setup.

The app has no built-in REST API, cloud file storage, or automatic multi-device file synchronization. PostgreSQL shares structured records only; for another computer to open an uploaded file, it must have access to the same managed files directory or a future shared-storage service must be added.

## Local paths and backup

- `EDUPILOT_DATA_DIR` selects the per-user application data folder.
- `EDUPILOT_DB_PATH` selects a SQLite database file when running without PostgreSQL.
- `EDUPILOT_DATABASE_URL` configures PostgreSQL and takes precedence over the saved connection URL.
- `EDUPILOT_FILES_DIR` selects the managed upload folder.

Without overrides, app data is stored in `%LOCALAPPDATA%\\EduPilot` on Windows, `~/Library/Application Support/EduPilot` on macOS, and `$XDG_DATA_HOME/edupilot` (or `~/.local/share/edupilot`) on Linux. Back up the SQLite database and the managed files folder together. PostgreSQL data needs a PostgreSQL backup; the local files directory must also be backed up separately.

## Security boundaries

- Passwords are stored as salted PBKDF2-SHA256 hashes; comparisons use constant-time checks.
- Data values are passed as SQL parameters. Faculty-only data operations check the account role in the data layer; student record queries are scoped to the signed-in user.
- Attendance QR tokens are section-bound, HMAC-SHA256 signed, and expire after five minutes. They do not prove student identity and can be shared during their validity window.
- Face recognition is disabled. Face detection alone is not used to identify a student.
- Managed uploads are extension-allowlisted, limited to 25 MB, copied under random names, and never executed as a program by EduPilot.
- The code runner has no network access, a read-only base filesystem, a temporary workspace, resource limits, and an execution timeout. It has no host-shell fallback.
- Practical exams persist an attempt deadline and autosave drafts. The fullscreen interface restricts normal in-app navigation but is not an OS kiosk and cannot prevent operating-system task switching or administrator actions.
- PostgreSQL mode is for a controlled, trusted network. Do not expose the database directly to the public internet. A production multi-user deployment needs an authenticated API, TLS, managed identity/access, and shared file storage.

## Supported and optional capabilities

Core desktop features use `requirements.txt`. Offline microphone recognition, text-to-speech, and camera scanning use optional dependencies from `requirements-optional.txt`; voice recognition also needs a separately installed Vosk model. Student code execution needs Docker and the `edupilot-runner` image. Face identity matching, OS-level exam lockdown, cloud synchronization, and automatic multi-device file sharing are not implemented.
