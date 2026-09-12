# EduPilot feature list

## 1. Separate sign-in

| Role | What the user sees |
|---|---|
| Faculty | Faculty Dashboard and authorised class/lab management tools |
| Student | Personal Dashboard showing only their own academic, attendance, and laboratory progress |

The current sign-in is a first-review prototype. The final version will authenticate users from approved local accounts and enforce role-based access.

## 2. Faculty features

| Feature | Purpose | First-review status |
|---|---|---|
| Faculty Dashboard | Daily classes, student attendance, lab readiness, pending reviews | UI prototype |
| Student Management | View student register number, name, class, and attendance; add/update records | Demo workspace |
| Attendance Taker | Mark each student present/absent and save the class register | Interactive demo; SQLite next |
| Academic Tracker | Class average, assignments, at-risk learners, and lab completion | UI prototype |
| Lab Assistant | Today's experiment, system status, Open VS Code, Lab Manual, mark completion | Interactive UI; real data next |
| AI Assistant | Course/manual help and safe voice/text commands | UI prototype |
| Reports | Attendance, marks, assignment, and lab reports | UI prototype |

## 3. Student features

| Feature | Purpose | First-review status |
|---|---|---|
| My Dashboard | Next class, attendance, pending work, and lab progress | UI prototype |
| My Academics | Internal marks, assignments, overall progress, and support alerts | UI prototype |
| My Attendance | Personal attendance percentage, present/absent record, and eligibility status | UI prototype |
| My Lab Progress | Completed experiments, record status, next experiment, and lab marks | UI prototype |
| Lab Assistant | Today's experiment, assigned system, Open VS Code, Lab Manual, mark completion | Interactive UI |
| AI Study Assistant | Answers sourced from approved course notes and lab manuals | Planned after knowledge base |
| My Reports | Personal attendance, academic, and lab summary | UI prototype |

## 4. Important implementation rules

- Student users can view only their own records.
- Faculty actions such as attendance marking, updates, and report export are logged.
- Voice commands are restricted to defined, confirmable actions.
- Course and lab answers use approved material; the assistant must not invent institutional details.
- Voice/transcript retention requires consent and follows a local-first design.
