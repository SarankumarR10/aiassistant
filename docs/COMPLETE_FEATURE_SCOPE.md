# EduPilot complete feature scope

This document is the approved feature scope for EduPilot, a local-first personal assistant for classrooms and computer laboratories. Features are grouped into implementation tracks so the project can be demonstrated honestly at each review.

## Implementation notes

The application now includes persistent role-based attendance, student academic marks, assignments and grading, lab submissions with faculty review, practical-exam publishing and timing, scoped reminders and notices, local course-document retrieval, data exports, and faculty/student workspaces. The following capabilities remain deliberately limited until their required models or safeguards exist:

- Voice commands can be entered as text or captured from the microphone with a configured local Vosk model and `sounddevice`. The model is not bundled; text-to-speech remains optional.
- Face attendance is disabled because face detection alone cannot identify a student. QR check-in uses signed, section-bound five-minute codes; students can scan locally with OpenCV or paste the token, then explicitly submit it for validation.
- The code runner requires the optional `edupilot-runner` Docker image. It uses no network, read-only base filesystem, a temporary workspace, memory/process limits, timeout, and explicit confirmation; it does not execute code directly on the host.
- Practical exam submissions and start/deadline times are saved locally and enforced on submission. Faculty can publish and close active practical exams. Screen locking remains disabled.
- Workstation metrics require `psutil`; PDF indexing requires `pypdf`; scannable QR rendering requires `qrcode`; Excel exports require `openpyxl`. Missing runtime dependencies are reported instead of replaced with sample data.
- Analytics and reports are based on recorded data. Empty data is shown as unavailable rather than as a fabricated percentage.
- Setup scripts check Python 3.10+ and detect a broken generated virtual environment; the run scripts report how to rebuild it.
- The offline tutor includes 23 curated starter FAQs across programming and core computer-science subjects. Faculty can extend the local knowledge base with approved notes and questions.
- Faculty and students have private, per-account notes with optional local Vosk dictation; transcript content is saved only when the user explicitly saves a note.

## Track A — Offline assistant and learning support

| Feature | Planned behaviour | Status |
|---|---|---|
| Offline Voice Assistant | Wake phrase: **“Hey VCET Assistant”** (also support “Hey EduPilot”), offline speech recognition, text-to-speech, and a command router | Typed command router, optional Vosk microphone capture, optional TTS; the local speech model must be configured separately |
| AI Programming Tutor | Explain OOP, DBMS, OS, CN, Java, Python, SQL, data structures, and algorithms | Offline search over 23 curated starter FAQs across those subjects, with faculty-managed local notes and question-bank material available to retrieval |
| Local Document Q&A (offline RAG) | Search approved PDFs, lab manuals, notes, and question banks; cite local source material in answers | Local text and extractable PDF chunks with source titles; no generative model |
| Smart Question Bank | Search unit-wise and previous-year questions | Faculty-managed local model and previous-year questions; student filters by subject, unit, source, and text; answers are available to cited local retrieval |
| Student Query Module | Timetable, next lab, room, and internal-exam queries | Local FAQ, approved-document, question-bank, next-class/lab, room, and role-filtered exam-notice answers with citations; reports missing timetable/notices instead of inventing dates |

## Track B — Attendance and analytics

| Feature | Planned behaviour | Status |
|---|---|---|
| Face Recognition Attendance | Faculty starts attendance; webcam matches enrolled faces and reports unknown faces | Disabled until consent, enrolment, identity matching, and retention rules exist |
| Voice Attendance backup | Assistant calls student names; student answers “Present” | Faculty can use typed/multi-student phrases or guided local roll call, which displays each unmarked name (and speaks it when optional offline TTS is available) before recording one clear spoken Present/Absent response; audio is not saved |
| QR Attendance | Webcam scans a student QR code when face recognition is unavailable | Signed, section-bound, expiring faculty QR; students can scan with the local camera or paste the code, review it, then submit for validation |
| Anti-proxy Attendance | One record per student per class session; combine verification methods for confidence | SQLite uniqueness rule in the local data design |
| Attendance Reports | Daily, weekly, monthly, and student-wise percentage; PDF/Excel export | Faculty attendance reports can filter by selected day/week/month or all dates, subject, and section; CSV/Excel/HTML/PDF exports and personal HTML/Excel transcripts are available |
| Classroom Analytics | Attendance, absentees, FAQs, lab use, and daily activity | Per-student attendance/absences and at-risk counts, aggregate assistant-query counts without storing prompts (90-day retention), today's attendance registers, lab submissions, assignment submissions, and schedule/exam query activity |

## Track C — Classroom and laboratory operations

| Feature | Planned behaviour | Status |
|---|---|---|
| Smart Classroom Control | Voice/text commands for PowerPoint, slides, lecture notes, timer, schedule, and optional LMS access | Typed command console supports confirmed allowlisted app launches, slide controls, countdown timers, schedules, notices, reminders, and local course queries; lecture-note/LMS controls remain unavailable |
| Smart Lab Assistant | Open VS Code, IntelliJ, Eclipse, Chrome, SQL Developer, Android Studio, Git Bash; create projects and run tools | Confirmed allowlisted app launches, guarded local starter-project creation, and isolated Code Runner; each optional local tool must be installed |
| Smart Lab Monitoring | CPU, RAM, disk, network, and running-application status | Live CPU, RAM, disk, network counters, and process data when `psutil` is installed |
| AI Lab Assistant | Compile code, explain errors, guide practical work | Code runner and error explanation phase |
| Code Runner | Run Java, Python, C, and C++ through the GUI/voice command | Voice commands open the matching editor; the user reviews the sample and confirms before restricted Docker execution (no network, resource limits, and timeout); Docker image setup is required |
| Lab Exam Assistant | Question paper, timer, submission, optional screen lock | Faculty publish/close workflow, active question display, persisted per-student timer/submission; screen lock is not implemented |

## Track D — Faculty and student experience

| Role | Features |
|---|---|
| Faculty | Dashboard, student list, attendance taker, timetable management, note/PDF/FAQ upload, academic tracker, reports, analytics, exam publishing, classroom control, lab tools |
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
- Face identity matching, screen locking, and LMS access are not enabled. They need hardware/service integration or additional privacy safeguards and are not represented as completed features.
- Live workstation metrics require `psutil`; PDF extraction requires `pypdf`; Excel exports require `openpyxl`; QR image rendering requires `qrcode`.
