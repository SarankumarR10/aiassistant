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
