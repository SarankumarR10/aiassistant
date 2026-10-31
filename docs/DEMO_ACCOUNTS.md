# EduPilot demo accounts

These accounts are created once when the academic database initializes. The initial credentials are for a classroom demonstration; change them before using the database with real student records.

## Faculty

| Name | Role | Username | Initial password |
| --- | --- | --- | --- |
| Dr. Meera Raman | Faculty | `faculty1` | `Faculty123!` |
| Prof. Arjun Menon | Faculty | `faculty2` | `Faculty123!` |
| Dr. Priya Nair | Faculty | `faculty3` | `Faculty123!` |

## Students

| Name | Role | Username | Initial password | Class |
| --- | --- | --- | --- | --- |
| Asha Kumar | Student | `student1` | `Student123!` | CSE, Year 1, Section A |
| Kavin Raj | Student | `student2` | `Student123!` | CSE, Year 1, Section A |
| Nila Devi | Student | `student3` | `Student123!` | CSE, Year 2, Section A |

The academic year is set to the current July-to-June year when the demo data is first seeded. Faculty teaching assignments are created for CS301 Data Structures, CS302 Database Management Systems, CS303 Computer Networks, and CS304 Python Programming.

On first startup after this update, EduPilot clears existing accounts and academic records, including attendance, marks, assignments, submissions, notices, schedules, audit history, private voice notes, face enrollments, and local device settings. Managed uploads are removed. The standard subject catalog, curated starter FAQ content, and shared app settings such as the QR signing key are retained. The six accounts above and their class and subject assignments are then created. The reset runs once per database.
