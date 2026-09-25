"""Offline retrieval from approved FAQs and locally indexed course documents."""
import os
import re
import sqlite3
from datetime import datetime
from database.database import (
    get_connection, _audit, get_timetables, get_announcements, record_assistant_query_event,
)


class OfflineRAGEngine:
    def ingest_file(self, title: str, file_path: str, subject_id: int = 1,
                    *, uploaded_by: int, unit_number: int = 1) -> int:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
                text = "\n\n".join(page.extract_text() or "" for page in PdfReader(file_path).pages)
            except ImportError as error:
                raise RuntimeError("Install pypdf to index PDF documents.") from error
        else:
            with open(file_path, "r", encoding="utf-8", errors="strict") as stream:
                text = stream.read()
        if not text.strip():
            raise ValueError("This document contains no extractable text to index.")
        return self.ingest_text_document(title, text, subject_id, file_path, uploaded_by, unit_number)

    def ingest_text_document(self, title: str, content: str, subject_id: int = 1,
                             file_path: str = "text_content", *, uploaded_by: int,
                             unit_number: int = 1) -> int:
        chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", content) if len(chunk.strip()) > 20]
        if not chunks and content.strip():
            chunks = [content.strip()]
        if not chunks:
            raise ValueError("There is no readable content to index.")
        conn = get_connection()
        try:
            c = conn.cursor()
            role = c.execute("SELECT role FROM users WHERE id = ?", (uploaded_by,)).fetchone()
            if not role or role[0] != "faculty":
                raise PermissionError("Only faculty can add course documents.")
            c.execute("INSERT INTO notes (subject_id, title, file_path, unit_number, uploaded_by) VALUES (?, ?, ?, ?, ?)",
                      (subject_id, title, file_path, unit_number, uploaded_by))
            c.execute("INSERT INTO documents (title, subject_id, file_path, uploaded_by) VALUES (?, ?, ?, ?)",
                      (title, subject_id, file_path, uploaded_by))
            doc_id = c.lastrowid
            c.executemany("INSERT INTO document_chunks (document_id, chunk_index, content, keywords) VALUES (?, ?, ?, ?)",
                          [(doc_id, idx, chunk, " ".join(re.findall(r"[\w]+", chunk.lower()))) for idx, chunk in enumerate(chunks)])
            _audit(c, uploaded_by, "note.uploaded_and_indexed", f"title={title}; document={doc_id}")
            conn.commit()
            return doc_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, user_question: str, *, role: str | None = None) -> dict:
        q = user_question.strip()
        terms = {word for word in re.findall(r"[\w]+", q.lower()) if len(word) > 2}
        if not terms:
            return {"answer": "Please enter a specific question about your course materials.", "source": "", "confidence": "Low"}
        schedule_answer = self._query_timetable(q)
        if schedule_answer:
            record_assistant_query_event("schedule")
            return schedule_answer
        q_lower = q.casefold()
        asks_exam_date = any(phrase in q_lower for phrase in (
            "internal exam", "exam schedule", "exam date", "when is the exam", "when is my exam",
            "when are exams", "exam timetable", "test date",
        ))
        if asks_exam_date:
            record_assistant_query_event("exam")
            notice_terms = ("internal",) if "internal" in q_lower else ("exam", "assessment", "test")
            exam_notices = [notice for notice in get_announcements(role)
                            if any(term in f"{notice[2]} {notice[3]}".casefold() for term in notice_terms)]
            if exam_notices:
                notice = exam_notices[0]
                return {"answer": f"{notice[2]}\n{notice[3]}",
                        "source": f"Department notice — {notice[1]}", "confidence": "High"}
            return {"answer": "There is no published internal-exam date in the local timetable or notices. Please check with faculty for the confirmed schedule.",
                    "source": "Local timetable and notices", "confidence": "Low"}
        record_assistant_query_event("learning")
        conn = get_connection()
        try:
            faqs = conn.execute("SELECT category, question, answer, keywords FROM faq_knowledge_base").fetchall()
            rows = conn.execute("""SELECT COALESCE(s.code, 'General'), d.title, dc.content
                FROM document_chunks dc JOIN documents d ON d.id = dc.document_id
                LEFT JOIN subjects s ON s.id = d.subject_id""").fetchall()
            question_rows = conn.execute("""SELECT s.code,
                'Question Bank — Unit ' || q.unit_number || ' — ' || q.source_kind ||
                    CASE WHEN q.exam_year IS NOT NULL THEN ' (' || q.exam_year || ')' ELSE '' END,
                q.question || char(10) || 'Model answer: ' || COALESCE(q.answer_key, '')
                FROM question_banks q JOIN subjects s ON s.id = q.subject_id""").fetchall()
            rows.extend(question_rows)
        finally:
            conn.close()
        faq_hits = []
        for category, question, answer, keywords in faqs:
            faq_terms = set(re.findall(r"[\w]+", f"{question} {category} {keywords or ''}".lower()))
            score = len(terms.intersection(faq_terms))
            if score:
                faq_hits.append((score, category, question, answer))
        if faq_hits:
            faq_hits.sort(key=lambda row: row[0], reverse=True)
            score, category, question, answer = faq_hits[0]
            if score / len(terms) >= 0.5:
                return {"answer": answer, "source": f"Local FAQ — {category}: {question}",
                        "confidence": "High" if score >= min(3, len(terms)) else "Medium"}
        scored = []
        for subject_code, title, content in rows:
            content_terms = set(re.findall(r"[\w]+", content.lower()))
            score = len(terms.intersection(content_terms))
            if score:
                scored.append((score, subject_code, title, content))
        scored.sort(key=lambda row: row[0], reverse=True)
        if not scored:
            return {"answer": "I couldn't find this topic in the approved local course materials. Try a more specific term or ask your faculty to add the relevant notes.",
                    "source": "No matching local source", "confidence": "Low"}
        best_score, subject_code, title, content = scored[0]
        return {"answer": content, "source": f"{subject_code} — {title}",
                "confidence": "High" if best_score >= min(3, len(terms)) else "Medium"}

    @staticmethod
    def _query_timetable(question: str) -> dict | None:
        text = question.casefold()
        next_lab = any(phrase in text for phrase in ("next lab", "upcoming lab", "when is my lab"))
        next_class = any(phrase in text for phrase in ("next class", "upcoming class", "next lecture"))
        asks_room = any(phrase in text for phrase in ("where is", "which room", "what room", "room for"))
        asks_schedule = any(phrase in text for phrase in ("timetable", "class schedule", "today's schedule", "today schedule"))
        if not (next_lab or next_class or asks_room or asks_schedule):
            return None
        rows = get_timetables()
        if next_lab:
            rows = [row for row in rows if "lab" in f"{row[2]} {row[6]}".casefold()]
        if asks_room and not next_lab and not next_class:
            match = next((row for row in rows
                          if row[1].casefold() in text or row[2].casefold() in text), None)
            rows = [match] if match else []
        if not rows:
            return {"answer": "No matching class or laboratory is listed in the local timetable. Ask faculty to update the schedule.",
                    "source": "Local timetable", "confidence": "Low"}
        now = datetime.now()
        weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
        today_index = now.weekday()
        upcoming = []
        for row in rows:
            try:
                day_index = weekdays.index(row[3])
                start = datetime.strptime(row[4], "%H:%M").time()
            except (ValueError, TypeError):
                continue
            delta = (day_index - today_index) % 7
            if delta == 0 and start <= now.time():
                delta = 7
            upcoming.append((delta, start, row))
        if not upcoming:
            return {"answer": "No upcoming class is listed in the local timetable.",
                    "source": "Local timetable", "confidence": "Low"}
        _, _, row = min(upcoming)
        label = "next lab" if next_lab else "next class"
        answer = f"Your {label} is {row[3]} from {row[4]} to {row[5]}: {row[1]} — {row[2]}, in {row[6]}."
        return {"answer": answer, "source": f"Timetable — {row[1]}", "confidence": "High"}


rag_engine = OfflineRAGEngine()
