# EduPilot complete feature scope

This document is the approved feature scope for EduPilot, a local-first personal assistant for classrooms and computer laboratories. Features are grouped into implementation tracks so the project can be demonstrated honestly at each review.

## Track A — Offline assistant and learning support

| Feature | Planned behaviour | Status |
|---|---|---|
| Offline Voice Assistant | Wake phrase: **“Hey VCET Assistant”** (also support “Hey EduPilot”), offline speech recognition, text-to-speech, and a command router | Foundation planned; Vosk model must be added locally |
| AI Programming Tutor | Explain OOP, DBMS, OS, CN, Java, Python, SQL, data structures, and algorithms | Local FAQ/knowledge base foundation |
| Local Document Q&A (offline RAG) | Search approved PDFs, lab manuals, notes, and question banks; cite local source material in answers | Local text/FAQ search foundation; PDF extraction next |
| Smart Question Bank | Search unit-wise and previous-year questions | Local question-bank collection next |
| Student Query Module | Timetable, next lab, room, and internal-exam queries | UI and local FAQ foundation |

## Track B — Attendance and analytics

| Feature | Planned behaviour | Status |
|---|---|---|
| Face Recognition Attendance | Faculty starts attendance; webcam matches enrolled faces and reports unknown faces | Optional camera/model integration; requires consent and face enrolment |
| Voice Attendance backup | Assistant calls student names; student answers “Present” | Voice workflow UI; Vosk integration next |
| QR Attendance | Webcam scans a student QR code when face recognition is unavailable | Optional camera/QR integration |
| Anti-proxy Attendance | One record per student per class session; combine verification methods for confidence | SQLite uniqueness rule in the local data design |
| Attendance Reports | Daily, weekly, monthly, and student-wise percentage; PDF/Excel export | Database/report-export phase |
| Classroom Analytics | Attendance, absentees, FAQs, lab use, and daily activity | Faculty analytics/report UI; data aggregation phase |

## Track C — Classroom and laboratory operations

| Feature | Planned behaviour | Status |
|---|---|---|
| Smart Classroom Control | Voice/text commands for PowerPoint, slides, lecture notes, timer, schedule, and optional LMS access | UI and safe command-routing phase |
| Smart Lab Assistant | Open VS Code, IntelliJ, Eclipse, Chrome, SQL Developer, Android Studio, Git Bash; create projects and run tools | Lab tool-launcher UI; each local tool must be installed |
| Smart Lab Monitoring | CPU, RAM, disk, network, and running-application status | System-health foundation next |
| AI Lab Assistant | Compile code, explain errors, guide practical work | Code runner and error explanation phase |
| Code Runner | Run Java, Python, C, and C++ through the GUI/voice command | Controlled local runner phase; must be sandboxed before shared use |
| Lab Exam Assistant | Question paper, timer, submission, optional screen lock | Exam workflow phase; screen lock needs institutional approval |

## Track D — Faculty and student experience

| Role | Features |
|---|---|
| Faculty | Dashboard, student list, attendance taker, timetable, note/PDF/FAQ upload, academic tracker, reports, analytics, classroom control, lab tools |
| Student | Personal attendance, timetable, notes, assignments, lab manuals, FAQ/question bank, reminders, lab progress, voice assistant |
| Both | Voice notes, smart reminders for assignment/exam/viva/lab submissions, role-based privacy, audit trail |

## Non-negotiable safeguards

1. Students can view only their own attendance, academics, reports, and submissions.
2. Face/voice data collection requires consent, an enrolment policy, retention limits, and a non-biometric attendance alternative.
3. Attendance allows only one record per student per session and retains the verification method (manual, face, voice, or QR).
4. File deletion, application launch, and code execution require an explicit user action and confirmation in the final product.
5. AI answers must be based on approved local materials and show the supporting source.
6. Screen locking, file deletion, LMS access, and all network actions remain disabled until explicitly approved and tested.

## Delivery order

1. Current: role-based UI, attendance register, student management, lab workspace.
2. Next: SQLite data, timetable, notes/reminders, student-specific data, reports.
3. Then: Vosk/pyttsx3 voice loop, local FAQ/document search, classroom commands.
4. Final: camera/QR attendance, system monitoring, secure code runner, analytics, usability evaluation.
