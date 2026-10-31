# EduPilot complete feature scope

This document is the approved feature scope for EduPilot, a local-first personal assistant for classrooms and computer laboratories. Features are grouped into implementation tracks so the project can be demonstrated honestly at each review.

## Implementation notes

The application includes persistent role-based attendance, class-scoped student and faculty records, subject allocations, academic marks, assignments and grading, scoped reminders and notices, local course-document retrieval, data exports, faculty/student workspaces, and structured online examinations with submitted-answer review and grading.

- The supported architecture is a local-first PySide6 desktop application. Screens call Python feature services directly; those services enforce role checks and use parameterized queries. SQLite works as a standalone store. When configured, PostgreSQL stores shared academic records; there is no REST server, web client, CORS policy, or remote identity provider in this project.
- Private voice notes and device settings live in local SQLite. Academic records use PostgreSQL when configured, or SQLite otherwise. Course documents and assignment attachments are copied into a managed local file directory, while the database stores opaque file keys and metadata. `EDUPILOT_DATA_DIR`, `EDUPILOT_DB_PATH`, and `EDUPILOT_FILES_DIR` can relocate data. Legacy project-folder SQLite databases are copied using SQLite's backup API on first launch.
- There is no automatic synchronization in SQLite-only mode. When multiple clients are configured to use the same PostgreSQL database, structured academic records are shared. Uploaded file contents are local by default; clients can share them by setting `EDUPILOT_FILES_DIR` to the same network folder on each computer.
- The managed storage service enforces a 25 MB upload ceiling, an extension allowlist, random file names, and path containment checks. EduPilot does not create or sync a shared folder, and cloud/S3 storage and signed URLs are not implemented.

- Voice commands can be entered as text or captured from the microphone with a configured local Vosk model and `sounddevice`. The model is not bundled; text-to-speech remains optional.
- Face attendance uses OpenCV contrib LBPH only after faculty confirms student opt-in and captures at least five samples. Encrypted samples stay in device-local SQLite; the encryption key stays in the OS credential vault. Samples are deleted after 90 days or when the student record is removed. Matching suggests one student; faculty must confirm before marking attendance. Camera matching does not detect photo spoofing or prove liveness, so signed QR and manual marking remain available. QR check-in uses signed, section-bound five-minute codes; students can scan locally with OpenCV or paste the token, then explicitly submit it for validation.
- The student code runner requires the optional `edupilot-runner` Docker image. It uses no network, read-only base filesystem, a temporary workspace, memory/process limits, timeout, and explicit confirmation; faculty do not have a code runner page.
- Practical exam attempts and deadlines are stored in the configured academic database and enforced on submission. Student exams use fullscreen mode, autosaved drafts that are hidden from faculty until final submission, automatic submission at timeout, and app-level navigation/close restrictions. Faculty can publish and close active practical exams. This desktop app does not lock down Windows or prevent OS-level task switching.
- The core installer includes `psutil`, `pypdf`, `qrcode`, and `openpyxl` for workstation metrics, PDF indexing, QR rendering, and spreadsheet exports. Microphone recognition, TTS, and camera tools are optional and listed in `requirements-optional.txt`.
- Analytics and reports are based on recorded data. Empty data is shown as unavailable rather than as a fabricated percentage.
- Student cohorts are grouped by department/program, year of study, section, and academic year. Faculty profiles hold staff ID, department, and designation; teaching assignments connect subjects and faculty to each class. Student-facing learning modules use the student's class, and faculty views use classes they created or teach. Existing records are migrated when their class can be determined without guessing.
- Setup scripts check Python 3.10+ and detect a broken generated virtual environment; the run scripts report how to rebuild it.
- The offline tutor includes 23 curated starter FAQs across programming and core computer-science subjects. Faculty can extend the local knowledge base with approved notes and questions.
- Faculty and students have private, per-account notes with optional local Vosk dictation; transcript content is saved only when the user explicitly saves a note.

## Track A — Offline assistant and learning support

| Feature | Planned behaviour | Status |
|---|---|---|
| Offline Voice Assistant | Wake phrase: **“Hey VCET Assistant”** (also support “Hey EduPilot”), offline speech recognition, text-to-speech, and a command router | Typed command router, optional Vosk microphone capture, optional TTS; the local speech model must be configured separately |
| AI Programming Tutor | Explain OOP, DBMS, OS, CN, Java, Python, SQL, data structures, and algorithms | Offline search over 23 curated starter FAQs across those subjects, with faculty-managed local notes and question-bank material available to retrieval |
| Local Document Q&A (offline RAG) | Search approved PDFs, lab manuals, notes, and question banks; cite local source material in answers | Faculty uploads UTF-8 text/Markdown or text-based PDFs. The app creates overlapping chunks, ranks them with offline BM25 term statistics, returns short grounded passages with document/page citations, and shows match confidence. Scanned PDFs need OCR before indexing; no generative model is bundled. |
| Smart Question Bank | Search unit-wise and previous-year questions | Faculty-managed local model and previous-year questions; student filters by subject, unit, source, and text; answers are available to cited local retrieval |
| Student Query Module | Timetable, next lab, room, and internal-exam queries | Local FAQ, approved-document, question-bank, next-class/lab, room, and role-filtered exam-notice answers with citations; reports missing timetable/notices instead of inventing dates |

## Track B — Attendance and analytics

| Feature | Planned behaviour | Status |
|---|---|---|
| Face Recognition Attendance | Faculty starts attendance; webcam matches enrolled faces and reports unknown faces | Optional OpenCV contrib LBPH matching; faculty confirms each candidate; opt-in enrollment is encrypted on-device, expires after 90 days, and can be deleted at any time |
| Voice Attendance backup | Assistant calls student names; student answers “Present” | Faculty can use typed/multi-student phrases or guided local roll call, which displays each unmarked name (and speaks it when optional offline TTS is available) before recording one clear spoken Present/Absent response; audio is not saved |
| QR Attendance | Webcam scans a student QR code when face recognition is unavailable | Signed, section-bound, expiring faculty QR; students can scan with the local camera or paste the code, review it, then submit for validation |
| Duplicate Attendance Prevention | One record per student per class session; combine verification methods for confidence | Database uniqueness rule prevents more than one record per student per session |
| Attendance Reports | Daily, weekly, monthly, and student-wise percentage; PDF/Excel export | Faculty attendance reports can filter by selected day/week/month or all dates, subject, and section; CSV/Excel/HTML/PDF exports and personal HTML/Excel transcripts are available |
| Classroom Analytics | Attendance, absentees, FAQs, lab use, and daily activity | Per-student attendance/absences and at-risk counts, aggregate assistant-query counts without storing prompts (90-day retention), today's attendance registers, lab submissions, assignment submissions, and schedule/exam query activity |

## Track C — Classroom and laboratory operations

| Feature | Planned behaviour | Status |
|---|---|---|
| Smart Classroom Control | Voice/text commands for PowerPoint, slides, lecture notes, timer, schedule, and optional LMS access | Typed command console supports confirmed allowlisted app launches, slide controls, countdown timers, schedules, notices, reminders, and local course queries; opening a matched course file requires user confirmation; LMS access remains unavailable |
| Smart Lab Assistant | Open VS Code, IntelliJ, Eclipse, Chrome, SQL Developer, Android Studio, Git Bash; create projects and run tools | Faculty voice console supports confirmed allowlisted app launches; student Code Runner is restricted and requires Docker; each optional local tool must be installed |
| Smart Lab Monitoring | CPU, RAM, disk, network, and running-application status | Live CPU, RAM, disk, network counters, and process data when `psutil` is installed |
| AI Lab Assistant | Compile code, explain errors, guide practical work | Code runner and error explanation phase |
| Code Runner | Run Java, Python, C, and C++ through the student GUI | Available in the student workspace; the user reviews the sample and confirms before restricted Docker execution (no network, resource limits, and timeout); Docker image setup is required |
| Online Exam Management | Faculty creates and publishes online exams; students complete a timed attempt; faculty reviews answers and marks | Faculty creates class- and subject-specific exams, authors structured questions, schedules and publishes exams, and reviews submitted answers/results. Students take timed fullscreen exams with autosave, timeout submission, and app-level navigation restrictions. It does not lock the operating system. |

## Track D — Faculty and student experience

| Role | Features |
|---|---|
| Faculty | Dashboard, class-structured student list, subject allocations, attendance, timetable, class-scoped course materials/RAG, academic records, assignments/grading, notices, analytics, and online exam authoring/review |
| Student | Personal attendance, timetable, notes, assignments, lab manuals, FAQ/question bank, reminders, lab submissions/progress, voice command console |
| Both | Private per-account notes with optional offline dictation, smart reminders for assignment/exam/viva/lab submissions, role-based privacy, audit trail |

## Non-negotiable safeguards

1. Students can view only their own attendance, academics, reports, and submissions.
2. Face/voice data collection requires consent, an enrolment policy, retention limits, and a non-biometric attendance alternative.
3. Attendance allows only one record per student per session and retains the verification method (manual, face, voice, or QR).
4. File deletion, application launch, and code execution require an explicit user action and confirmation in the final product.
5. AI answers must be based on approved local materials and show the supporting source.
6. Screen locking, file deletion, LMS access, and all network actions remain disabled until explicitly approved and tested.

## Deployment and remaining work

- Core desktop workflows and role-based data modules are implemented. Faculty and student pages have been rendered at the supported minimum window size.
- Offline microphone input requires `sounddevice` and a separately supplied Vosk model. Guided roll call, note dictation, and QR camera scanning require local microphone/camera access; typed notes, typed attendance phrases, and pasted signed QR codes remain available as fallbacks.
- The restricted code runner requires Docker and the documented `edupilot-runner` image.
- Face attendance needs the optional `opencv-contrib-python` and `cryptography` packages plus a camera; each student must opt in and be enrolled on that device. OS-level screen locking and LMS access are not enabled.
- The standard requirements install includes workstation metrics (`psutil`), PDF extraction (`pypdf`), Excel exports (`openpyxl`), and QR image rendering (`qrcode`). Optional speech and camera dependencies are listed separately.
