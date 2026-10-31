from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: int
    username: str
    role: str
    name: str

@dataclass
class Student:
    id: int
    user_id: int
    roll_number: str
    name: str
    department: str
    year: int
    section: str = "C"
    class_id: Optional[int] = None

@dataclass
class AcademicClass:
    id: int
    department: str
    year_of_study: int
    section: str
    academic_year: str

@dataclass
class FacultyProfile:
    user_id: int
    employee_code: Optional[str]
    department: str
    designation: str

@dataclass
class TeachingAssignment:
    id: int
    class_id: int
    subject_id: int
    faculty_id: int
    academic_term: str = "Full Year"

@dataclass
class Subject:
    id: int
    code: str
    name: str

@dataclass
class TimetableEntry:
    id: int
    subject_code: str
    subject_name: str
    day_of_week: str
    start_time: str
    end_time: str
    room: str

@dataclass
class Assignment:
    id: int
    subject_code: str
    subject_name: str
    title: str
    description: str
    due_date: str
    max_marks: int = 100

@dataclass
class LabExperiment:
    id: int
    subject_code: str
    subject_name: str
    exp_number: int
    title: str
    description: str
    manual_path: Optional[str] = None

@dataclass
class Announcement:
    id: int
    faculty_name: str
    title: str
    content: str
    target_group: str
    created_at: str
