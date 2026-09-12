# EduPilot: Local-First Personal Assistant for Classrooms and Computer Laboratories

> **First-review working draft**  
> Team members: *[add names and roll numbers]*  
> Guide: *[add guide name]*

## 1. Problem statement and motivation

Faculty members repeatedly switch between attendance registers, student records, assignment trackers, laboratory schedules, computer-system status, and course material. These separate workflows consume class time and make it harder to identify students who need help. Existing general-purpose assistants also do not understand an institution's authorised class, student, and laboratory context.

EduPilot addresses this problem with a faculty-controlled, local-first desktop assistant that brings classroom and laboratory operations into one place. It will accept concise text or voice commands, surface timely information, and keep the human faculty member in control of every academic decision.

## 2. Objectives

1. Provide one desktop workspace for classrooms, attendance, student progress, labs, reports, and academic help.
2. Reduce repetitive faculty actions through guided voice/text commands such as “start attendance” and “open Java Lab manual”.
3. Identify attendance and academic-risk signals early through clear, explainable dashboards.
4. Support laboratory readiness, experiment progress, and maintenance follow-up.
5. Keep student information private through local-first storage, role controls, activity logs, and explicit faculty approval for actions.
6. Provide separate student and faculty experiences so that students see only their own academic/attendance/lab progress while faculty manage authorised class and lab operations.

## 3. Proposed methodology

EduPilot will be developed incrementally.

1. **Interface prototype:** PySide6 desktop shell, responsive navigation, dashboard, and faculty workflows (current stage).
2. **Data layer:** SQLite database for students, attendance, marks, assignments, experiments, equipment status, and audit logs.
3. **Workflow modules:** Student management, attendance, academic tracking, laboratory management, reports, and settings.
4. **Voice layer:** Offline speech recognition with Vosk; commands are passed to a safe intent router. pyttsx3 will provide optional spoken confirmation.
5. **Knowledge assistant:** Approved course notes and lab manuals are indexed locally. Answers will quote or link to their source material rather than inventing institutional facts.
6. **Evaluation:** Measure task-completion time, voice-command recognition accuracy, response usefulness, and usability feedback from faculty/student volunteers. Use only consented, anonymised data.

## 4. Expected outcome

A working desktop application that lets an authorised faculty member:

- view class and laboratory status at a glance;
- manage students and record attendance;
- review marks, assignments, and at-risk indicators;
- track laboratory sessions, systems, and experiments;
- generate attendance, academic, and lab reports; and
- ask grounded academic or lab-manual questions through a local-first assistant.

Students will have a separate sign-in and personal dashboard for their own attendance, academic tracker, pending assignments, lab progress, today’s experiment, and AI study support. They will not see other students’ records.

## 5. Literature review

| Paper | Key finding | How EduPilot uses it |
|---|---|---|
| Ramandanis & Xinogalos (2023), *Investigating the Support Provided by Chatbots to Educational Institutions and Their Students* | Educational chatbots commonly support both learning and institutional services, but adoption needs careful role design. | Combines student support with faculty workflows rather than treating the assistant as a generic chatbot. |
| Ramandanis & Xinogalos (2023), *Designing a Chatbot for Contemporary Education* | A systematic review identifies design considerations for educational conversational agents. | Uses domain-specific commands, transparent responses, and faculty review points. |
| Sajja et al. (2023), *Platform-Independent and Curriculum-Oriented Intelligent Assistant for Higher Education* | Course-aware assistants can reduce logistical barriers and answer curriculum questions. | Grounds answers in approved course notes and laboratory manuals. |
| Jacobs & Kiesler (2025), *GenAI Voice Mode in Programming Education* | Voice tutoring can aid programming tasks but requires accuracy safeguards, especially around code. | Voice is limited to confirmed commands; code and academic answers remain source-grounded. |
| Pardo, Cánovas & García Clemente (2025), *Audio Features in Education* | Educational audio systems need actionable feedback, privacy, and interpretable outputs. | Uses minimal voice data, local processing where possible, and clear user-facing status rather than surveillance analytics. |

## 6. Novelty and contribution

EduPilot is not presented as an autonomous teacher or an unrestricted chatbot. Its contribution is a **local-first, faculty-in-the-loop assistant that unifies classroom and lab operations with source-grounded academic support**. The same interface supports attendance, learner follow-up, laboratory readiness, reports, and approved course/lab knowledge.

Key differentiators:

- Classroom and laboratory workflows in one desktop assistant
- Local-first data handling and consent-aware design
- Voice commands only for well-defined, auditable actions
- Source-grounded course/lab answers instead of unsupervised institutional claims
- Explainable academic-risk indicators for faculty review, not automated grading

## 7. System architecture

```text
Faculty / Student
      |
Text UI + Optional Voice Input
      |
EduPilot Desktop Interface (PySide6)
      |
Command Router ------ Knowledge Assistant
      |                     |
Classroom | Attendance | Academic | Lab | Reports
      |                     |
SQLite Database <--- Approved Notes and Lab Manuals
      |
Audit Log, Role Checks, Export Controls
```

## 8. Implementation plan and milestones

| Phase | Deliverable | Status |
|---|---|---|
| 1 | EduPilot identity, desktop UI, dashboard, navigation prototype | Complete for first review |
| 2 | SQLite schema and Student Management | Planned |
| 3 | Attendance workflow and reports | Planned |
| 4 | Academic tracking, risk indicators, assignment status | Planned |
| 5 | Laboratory readiness and experiment tracking | Planned |
| 6 | Offline voice commands and safe confirmations | Planned |
| 7 | Grounded AI assistant, evaluation, privacy review, final report | Planned |

## 9. Intended paper

**Working title:** *EduPilot: A Local-First Faculty Assistant for Integrated Classroom and Laboratory Operations*

**Candidate venue:** *International Journal of Information and Education Technology (IJIET).* Its stated scope includes computing education and the use of ICT in education, which fits a measured study of EduPilot’s faculty workflow, offline voice interface, and usability evaluation. The final submission choice will be confirmed with the guide after the implementation and evaluation results are complete.

## 10. References

1. D. Ramandanis and S. Xinogalos, “Investigating the Support Provided by Chatbots to Educational Institutions and Their Students: A Systematic Literature Review,” *Multimodal Technologies and Interaction*, 7(11), 103, 2023. https://doi.org/10.3390/mti7110103
2. D. Ramandanis and S. Xinogalos, “Designing a Chatbot for Contemporary Education: A Systematic Literature Review,” *Information*, 14(9), 503, 2023. https://doi.org/10.3390/info14090503
3. R. Sajja, Y. Sermet, D. Cwiertny, and I. Demir, “Platform-Independent and Curriculum-Oriented Intelligent Assistant for Higher Education,” arXiv:2302.09294, 2023. https://arxiv.org/abs/2302.09294
4. S. Jacobs and N. Kiesler, “GenAI Voice Mode in Programming Education,” arXiv:2509.10596, 2025. https://arxiv.org/abs/2509.10596
5. F. Pardo, Ó. Cánovas, and F. J. García Clemente, “Audio Features in Education: A Systematic Review of Computational Applications and Research Gaps,” *Applied Sciences*, 15(12), 6911, 2025. https://doi.org/10.3390/app15126911
