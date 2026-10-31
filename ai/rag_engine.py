"""Offline retrieval and grounded answers from faculty-approved course material."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import get_close_matches

from database.database import (
    get_connection,
    _audit,
    get_timetables,
    get_announcements,
    record_assistant_query_event,
)
from storage.local_storage import storage_service


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[+#]+)?", re.IGNORECASE)
_STOP_WORDS = frozenset("""
    a an and are as at be been being but by can could did do does doing for from had has have
    having how i in into is it its may me might my of on or our please should so than that the
    their them then there these they this those to was we were what when where which who why will
    with would you your explain tell describe give show find about according based use used using
""".split())
_ALIASES = {
    "normalisation": "normalization",
    "normalise": "normalization",
    "normalize": "normalization",
    "normalised": "normalization",
    "normalized": "normalization",
    "normalising": "normalization",
    "normalizing": "normalization",
    "colour": "color",
    "define": "definition",
    "meaning": "definition",
    "purpose": "use",
    "function": "use",
    "functions": "use",
    "advantages": "benefit",
    "disadvantages": "limitation",
    "pros": "benefit",
    "cons": "limitation",
}


def _tokens(text: str) -> list[str]:
    """Normalize terms while retaining short programming-language names like C and R."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    result = []
    for raw in _TOKEN_RE.findall(text.casefold()):
        token = _ALIASES.get(raw, raw)
        if token in _STOP_WORDS:
            continue
        if len(token) > 5 and token.endswith("ies"):
            token = token[:-3] + "y"
        elif len(token) > 5 and token.endswith("ing"):
            token = token[:-3]
            if len(token) > 2 and token[-1] == token[-2]:
                token = token[:-1]
        elif len(token) > 4 and token.endswith("ied"):
            token = token[:-3] + "y"
        elif len(token) > 4 and token.endswith("ed"):
            token = token[:-2]
        elif len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
            token = token[:-1]
        if token and token not in _STOP_WORDS:
            result.append(token)
    return result


def _split_long_text(text: str, max_chars: int = 1100, overlap: int = 140) -> list[str]:
    """Split readable text on sentence/word boundaries and keep a small overlap."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            words = sentence.split()
            fragments: list[str] = []
            fragment = ""
            fragment_limit = max(1, max_chars - overlap)
            for word in words:
                candidate = f"{fragment} {word}".strip()
                if len(candidate) > fragment_limit and fragment:
                    fragments.append(fragment)
                    fragment = word
                else:
                    fragment = candidate
            if fragment:
                fragments.append(fragment)
            sentences_for_chunk = fragments
        else:
            sentences_for_chunk = [sentence]

        for part in sentences_for_chunk:
            candidate = f"{current} {part}".strip()
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
                tail = current[-overlap:]
                first_space = tail.find(" ")
                current = tail[first_space + 1:] if first_space >= 0 else tail
            candidate = f"{current} {part}".strip()
            if len(candidate) > max_chars:
                current = part[-max_chars:]
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _split_document(content: str, page_texts: list[str] | None = None) -> list[tuple[int | None, str]]:
    """Return (PDF page, chunk) pairs; text and Markdown have no page number."""
    if page_texts is not None:
        result = []
        for page_number, page_text in enumerate(page_texts, start=1):
            result.extend((page_number, chunk) for chunk in _split_long_text(page_text))
        return result

    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    if not paragraphs:
        paragraphs = [normalized.strip()]

    result: list[tuple[int | None, str]] = []
    current = ""
    for paragraph in paragraphs:
        for part in _split_long_text(paragraph):
            candidate = f"{current} {part}".strip()
            if len(candidate) <= 1100:
                current = candidate
            else:
                if current:
                    result.extend((None, chunk) for chunk in _split_long_text(current))
                current = part
    if current:
        result.extend((None, chunk) for chunk in _split_long_text(current))
    return result


class OfflineRAGEngine:
    """Index text/PDF sources and answer from ranked, cited local passages."""

    def ingest_file(
        self,
        title: str,
        file_path: str,
        subject_id: int = 1,
        *,
        uploaded_by: int,
        unit_number: int = 1,
        class_id: int | None = None,
    ) -> int:
        title = self._validate_document_fields(title, subject_id, unit_number)
        conn = get_connection()
        try:
            role = conn.execute("SELECT role FROM users WHERE id = ?", (uploaded_by,)).fetchone()
        finally:
            conn.close()
        if not role or role[0] != "faculty":
            raise PermissionError("Only faculty can add course documents.")

        reference = storage_service.store_file(
            file_path,
            uploaded_by=uploaded_by,
            category="course_materials",
            allowed_extensions={".pdf", ".txt", ".md"},
            max_bytes=25 * 1024 * 1024,
        )
        stored_path = storage_service.resolve(reference)
        try:
            if stored_path.suffix.lower() == ".pdf":
                try:
                    from pypdf import PdfReader
                except ImportError as error:
                    raise RuntimeError("Install pypdf to index PDF documents.") from error
                try:
                    reader = PdfReader(str(stored_path))
                    page_texts = [page.extract_text() or "" for page in reader.pages]
                except Exception as error:
                    raise ValueError(f"Could not read this PDF: {error}") from error
                text = "\n".join(page_texts)
                chunks = _split_document(text, page_texts=page_texts)
            else:
                try:
                    with stored_path.open("r", encoding="utf-8-sig", errors="strict") as stream:
                        text = stream.read()
                except UnicodeDecodeError as error:
                    raise ValueError("This text file is not UTF-8 encoded. Save it as UTF-8 and upload it again.") from error
                chunks = _split_document(text)

            if not any(_tokens(chunk) for _, chunk in chunks):
                raise ValueError("This document contains no searchable text. Scanned PDFs need OCR before they can be indexed.")
            return self._save_document(title, chunks, subject_id, reference, uploaded_by, unit_number, class_id)
        except Exception:
            storage_service.remove(reference)
            raise

    def ingest_text_document(
        self,
        title: str,
        content: str,
        subject_id: int = 1,
        file_path: str = "text_content",
        *,
        uploaded_by: int,
        unit_number: int = 1,
        class_id: int | None = None,
    ) -> int:
        title = self._validate_document_fields(title, subject_id, unit_number)
        chunks = _split_document(content)
        if not any(_tokens(chunk) for _, chunk in chunks):
            raise ValueError("There is no readable, searchable content to index.")
        return self._save_document(title, chunks, subject_id, file_path, uploaded_by, unit_number, class_id)

    @staticmethod
    def _validate_document_fields(title: str, subject_id: int, unit_number: int) -> str:
        title = (title or "").strip()
        if not title:
            raise ValueError("Enter a title for the course document.")
        if len(title) > 200:
            raise ValueError("Document titles are limited to 200 characters.")
        if subject_id is None:
            raise ValueError("Select a subject for the course document.")
        if not 1 <= int(unit_number) <= 20:
            raise ValueError("Choose a valid unit number.")
        return title

    @staticmethod
    def _save_document(title: str, chunks: list[tuple[int | None, str]], subject_id: int,
                       file_path: str, uploaded_by: int, unit_number: int,
                       class_id: int | None = None) -> int:
        conn = get_connection()
        try:
            role = conn.execute("SELECT role FROM users WHERE id = ?", (uploaded_by,)).fetchone()
            if not role or role[0] != "faculty":
                raise PermissionError("Only faculty can add course documents.")
            if not conn.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone():
                raise ValueError("Select a valid subject.")
            if class_id is not None and not conn.execute("""SELECT 1 FROM teaching_assignments
                WHERE class_id = ? AND subject_id = ? AND faculty_id = ?""",
                (class_id, subject_id, uploaded_by)).fetchone():
                raise PermissionError("This subject is not assigned to you for the selected class.")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notes (subject_id, title, file_path, unit_number, uploaded_by, class_id) VALUES (?, ?, ?, ?, ?, ?)",
                (subject_id, title, file_path, unit_number, uploaded_by, class_id),
            )
            cursor.execute(
                "INSERT INTO documents (title, subject_id, file_path, uploaded_by, class_id) VALUES (?, ?, ?, ?, ?)",
                (title, subject_id, file_path, uploaded_by, class_id),
            )
            document_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO document_chunks (document_id, chunk_index, content, keywords, page_number) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (document_id, index, chunk, " ".join(_tokens(chunk)), page_number)
                    for index, (page_number, chunk) in enumerate(chunks)
                ],
            )
            _audit(cursor, uploaded_by, "course_document.indexed",
                   f"document={document_id}; chunks={len(chunks)}; title={title}")
            conn.commit()
            return document_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, user_question: str, *, role: str | None = None, user_id: int | None = None,
              class_id: int | None = None) -> dict:
        question = (user_question or "").strip()
        query_terms = _tokens(question)
        if not query_terms:
            return self._result(
                "Enter a question with a course topic or keyword.", "", "Low", [],
            )

        schedule_answer = self._query_timetable(question, role=role, user_id=user_id)
        if schedule_answer:
            record_assistant_query_event("schedule", user_id=user_id, class_id=class_id)
            return schedule_answer

        lower_question = question.casefold()
        asks_exam_date = any(phrase in lower_question for phrase in (
            "internal exam", "exam schedule", "exam date", "when is the exam",
            "when is my exam", "when are exams", "exam timetable", "test date",
        ))
        if asks_exam_date:
            record_assistant_query_event("exam", user_id=user_id, class_id=class_id)
            notice_terms = ("internal",) if "internal" in lower_question else ("exam", "assessment", "test")
            notices = [notice for notice in get_announcements(role, user_id=user_id)
                       if any(term in f"{notice[2]} {notice[3]}".casefold() for term in notice_terms)]
            if notices:
                notice = notices[0]
                citation = {"source": f"Department notice — {notice[1]}", "page": None}
                return self._result(f"{notice[2]}\n{notice[3]}", citation["source"], "High", [citation])
            return self._result(
                "There is no published exam date in the local notices. Please check with faculty for the confirmed schedule.",
                "Local department notices", "Low", [],
            )

        record_assistant_query_event("learning", user_id=user_id, class_id=class_id)
        if role == "student" and user_id is not None and class_id is None:
            from database.database import get_student_class_id
            class_id = get_student_class_id(user_id)
            # A student without enrollment may search only globally shared material.
            # A non-matching sentinel prevents class-specific content from being treated as global.
            if class_id is None:
                class_id = -1
        candidates = self._load_candidates(
            class_id=class_id, faculty_id=user_id if role == "faculty" else None
        )
        if not candidates:
            return self._result(
                "No course material has been indexed yet. Ask faculty to upload notes or add questions to the question bank.",
                "No indexed course material", "Low", [],
            )

        query_terms = self._expand_query_terms(query_terms, candidates)
        ranked = self._rank(query_terms, candidates)
        if not ranked:
            return self._result(
                "I couldn't find this topic in the approved local material. Try a more specific course term or ask faculty to add the relevant notes.",
                "No matching local source", "Low", [],
            )

        best_coverage = ranked[0]["coverage"]
        if best_coverage < 0.25:
            return self._result(
                "I found only a weak match, so I can't give a reliable answer from the available material. Try a more specific term or ask faculty to add the relevant notes.",
                "No reliable match", "Low", [],
            )

        # Return a small set of independent supporting passages, not an entire
        # source document. Keep only evidence close to the best BM25 result.
        selected: list[dict] = []
        seen = set()
        cutoff = ranked[0]["score"] * 0.52
        for item in ranked:
            if item["score"] < cutoff or len(selected) == 3:
                break
            key = (item["source"], item["page"], item["content"])
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)

        citations = [{"source": item["source"], "page": item["page"]} for item in selected]
        passages = [self._extract_passage(item["content"], query_terms) for item in selected]
        answer = self._structure_answer(passages)
        source_text = "; ".join(self._format_citation(item) for item in citations)
        if best_coverage >= 0.65:
            confidence = "High"
        elif best_coverage >= 0.4:
            confidence = "Medium"
        else:
            confidence = "Low"
        return self._result(answer or selected[0]["content"], source_text, confidence, citations)

    @staticmethod
    def _expand_query_terms(query_terms: list[str], candidates: list[dict]) -> list[str]:
        """Correct clear single-word transcription/spelling slips using indexed vocabulary."""
        vocabulary = set()
        for item in candidates:
            vocabulary.update(_tokens(item["search_text"]))
        expanded = list(query_terms)
        for term in query_terms:
            if term in vocabulary or len(term) < 4:
                continue
            matches = get_close_matches(term, vocabulary, n=2, cutoff=0.82)
            if len(matches) == 1:
                expanded.append(matches[0])
        return expanded

    @staticmethod
    def _load_candidates(class_id: int | None = None,
                         faculty_id: int | None = None) -> list[dict]:
        conn = get_connection()
        try:
            document_conditions = []
            document_params = []
            if class_id is not None:
                document_conditions.append("(d.class_id IS NULL OR d.class_id = ?)")
                document_params.append(class_id)
            if faculty_id is not None:
                document_conditions.append(
                    "(d.class_id IS NULL OR d.class_id IN "
                    "(SELECT class_id FROM teaching_assignments WHERE faculty_id = ?))"
                )
                document_params.append(faculty_id)
            document_query = """SELECT COALESCE(s.code, 'General'), d.title,
                    COALESCE(n.unit_number, 1), dc.content, dc.page_number
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                LEFT JOIN subjects s ON s.id = d.subject_id
                LEFT JOIN notes n ON n.file_path = d.file_path AND n.title = d.title
            """
            if document_conditions:
                document_query += " WHERE " + " AND ".join(document_conditions)
            rows = conn.execute(
                document_query + " ORDER BY d.id, dc.chunk_index", tuple(document_params)
            ).fetchall()
            faqs = conn.execute(
                "SELECT category, question, answer, keywords FROM faq_knowledge_base"
            ).fetchall()
            question_conditions = []
            question_params = []
            if class_id is not None:
                question_conditions.append("(q.class_id IS NULL OR q.class_id = ?)")
                question_params.append(class_id)
            if faculty_id is not None:
                question_conditions.append(
                    "(q.class_id IS NULL OR q.class_id IN "
                    "(SELECT class_id FROM teaching_assignments WHERE faculty_id = ?))"
                )
                question_params.append(faculty_id)
            question_query = """SELECT s.code, q.unit_number, q.source_kind,
                    q.exam_year, q.question, COALESCE(q.answer_key, '')
                FROM question_banks q JOIN subjects s ON s.id = q.subject_id"""
            if question_conditions:
                question_query += " WHERE " + " AND ".join(question_conditions)
            questions = conn.execute(question_query, tuple(question_params)).fetchall()
        finally:
            conn.close()

        candidates = []
        for subject, title, unit, content, page in rows:
            candidates.append({
                "subject": subject, "title": title, "unit": unit, "page": page,
                "content": content, "source": f"{subject} — {title}",
                "search_text": f"{subject} {title} unit {unit} {content}",
            })
        for category, question, answer, keywords in faqs:
            candidates.append({
                "subject": "FAQ", "title": question, "unit": None, "page": None,
                "content": answer, "source": f"Local FAQ — {category}: {question}",
                "search_text": f"{category} {question} {keywords or ''} {answer}",
            })
        for subject, unit, source_kind, year, question, answer in questions:
            qualifier = f" ({year})" if year else ""
            title = f"Question Bank — Unit {unit} — {source_kind}{qualifier}"
            candidates.append({
                "subject": subject, "title": title, "unit": unit, "page": None,
                "content": f"Question: {question}\nModel answer: {answer}".strip(),
                "source": f"{subject} — {title}",
                "search_text": f"{subject} {title} {question} {answer}",
            })
        return candidates

    @staticmethod
    def _rank(query_terms: list[str], candidates: list[dict]) -> list[dict]:
        unique_query = set(query_terms)
        tokenized = [_tokens(item["search_text"]) for item in candidates]
        frequencies = [Counter(tokens) for tokens in tokenized]
        lengths = [len(tokens) for tokens in tokenized]
        count = len(candidates)
        average_length = max(sum(lengths) / max(count, 1), 1.0)
        document_frequency = Counter(
            term for tokens in tokenized for term in set(tokens)
        )
        ranked = []
        k1, b = 1.5, 0.75
        for item, tokens, term_counts, length in zip(candidates, tokenized, frequencies, lengths):
            matched = unique_query.intersection(term_counts)
            coverage = len(matched) / max(len(unique_query), 1)
            score = 0.0
            for term in unique_query:
                tf = term_counts.get(term, 0)
                if not tf:
                    continue
                df = document_frequency[term]
                idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
                score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * length / average_length))
            title_terms = set(_tokens(
                f"{item['subject']} {item['title']} unit {item.get('unit') or ''}"
            ))
            score += 0.35 * len(unique_query.intersection(title_terms))
            content_terms = set(_tokens(item["content"]))
            if len(unique_query) >= 2 and unique_query.issubset(content_terms):
                score *= 1.25
            if score > 0:
                ranked.append({**item, "score": score, "coverage": coverage,
                               "matched_terms": len(matched)})
        ranked.sort(key=lambda item: (item["score"], item["coverage"]), reverse=True)
        return ranked

    @staticmethod
    def _extract_passage(content: str, query_terms: list[str], limit: int = 900) -> str:
        text = re.sub(r"\s+", " ", content or "").strip()
        if len(text) <= limit:
            return text
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        if not sentences:
            return text[:limit].rsplit(" ", 1)[0] + "…"
        query = set(query_terms)
        scored = []
        for index, sentence in enumerate(sentences):
            sentence_terms = set(_tokens(sentence))
            overlap = len(query.intersection(sentence_terms))
            if overlap:
                density = overlap / max(len(sentence_terms), 1)
                scored.append((overlap, density, index, sentence))
        if not scored:
            return text[:limit].rsplit(" ", 1)[0] + "…"
        selected = []
        used = 0
        for _, _, index, sentence in sorted(scored, key=lambda row: (-row[0], -row[1], row[2])):
            if used + len(sentence) + 1 > limit:
                continue
            selected.append((index, sentence))
            used += len(sentence) + 1
            if used >= limit * 0.75:
                break
        excerpt = " ".join(sentence for _, sentence in sorted(selected))
        return excerpt or text[:limit].rsplit(" ", 1)[0] + "…"

    @staticmethod
    def _structure_answer(passages: list[str]) -> str:
        """Arrange retrieved evidence into readable sections without adding facts."""
        sentences: list[str] = []
        seen: set[str] = set()
        for passage in passages:
            text = re.sub(r"\s+", " ", passage or "").strip()
            # Question-bank passages store the prompt and answer together. Keep
            # the answer portion so a generated reply does not restate the prompt.
            text = re.sub(r"^.*?\bModel answer:\s*", "", text, flags=re.IGNORECASE)
            parts = re.split(r"(?<=[.!?])\s+", text)
            for part in parts:
                part = part.strip(" •\t")
                key = re.sub(r"\W+", " ", part.casefold()).strip()
                if part and key and key not in seen:
                    seen.add(key)
                    sentences.append(part)

        if not sentences:
            return "I couldn't extract a readable answer from the matching course material."

        example_pattern = re.compile(
            r"\b(?:for example|for instance|e\.g\.|example\s*[:\-]|consider the following)\b",
            re.IGNORECASE,
        )
        explanations = [sentence for sentence in sentences if not example_pattern.search(sentence)]
        examples = [sentence for sentence in sentences if example_pattern.search(sentence)]

        # A passage made entirely of examples can still answer the question;
        # show it once as the answer instead of duplicating it below.
        if not explanations:
            explanations, examples = sentences[:1], sentences[1:]

        answer_sentences = explanations[:1]
        detail_sentences = explanations[1:]
        sections = ["Answer\n" + " ".join(answer_sentences)]
        if detail_sentences:
            sections.append("Explanation\n" + "\n".join(f"• {sentence}" for sentence in detail_sentences))
        if examples:
            sections.append("Example\n" + "\n".join(f"• {sentence}" for sentence in examples))
        return "\n\n".join(sections)

    @staticmethod
    def _format_citation(citation: dict) -> str:
        return f"{citation['source']} (p. {citation['page']})" if citation.get("page") else citation["source"]

    @staticmethod
    def _result(answer: str, source: str, confidence: str, citations: list[dict]) -> dict:
        return {
            "answer": answer,
            "source": source,
            "confidence": confidence,
            "citations": citations,
        }

    @staticmethod
    def _query_timetable(question: str, *, role: str | None = None,
                         user_id: int | None = None) -> dict | None:
        text = question.casefold()
        next_lab = any(phrase in text for phrase in ("next lab", "upcoming lab", "when is my lab"))
        next_class = any(phrase in text for phrase in ("next class", "upcoming class", "next lecture"))
        asks_room = any(phrase in text for phrase in ("where is", "which room", "what room", "room for"))
        asks_schedule = any(phrase in text for phrase in ("timetable", "class schedule", "today's schedule", "today schedule"))
        if not (next_lab or next_class or asks_room or asks_schedule):
            return None

        if role == "student" and user_id is not None:
            rows = get_timetables(student_user_id=user_id)
        elif role == "faculty" and user_id is not None:
            rows = get_timetables(faculty_id=user_id)
        else:
            rows = get_timetables()
        if next_lab:
            rows = [row for row in rows if "lab" in f"{row[2]} {row[6]}".casefold()]
        if asks_room and not next_lab and not next_class:
            match = next((row for row in rows if row[1].casefold() in text or row[2].casefold() in text), None)
            rows = [match] if match else []
        if not rows:
            return OfflineRAGEngine._result(
                "No matching class or laboratory is listed in the local timetable. Ask faculty to update the schedule.",
                "Local timetable", "Low", [],
            )

        now = datetime.now()
        weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
        upcoming = []
        for row in rows:
            try:
                day_index = weekdays.index(row[3])
                start = datetime.strptime(row[4], "%H:%M").time()
            except (ValueError, TypeError):
                continue
            delta = (day_index - now.weekday()) % 7
            if delta == 0 and start <= now.time():
                delta = 7
            upcoming.append((delta, start, row))
        if not upcoming:
            return OfflineRAGEngine._result("No upcoming class is listed in the local timetable.", "Local timetable", "Low", [])
        _, _, row = min(upcoming)
        label = "next lab" if next_lab else "next class"
        answer = f"Your {label} is {row[3]} from {row[4]} to {row[5]}: {row[1]} — {row[2]}, in {row[6]}."
        return OfflineRAGEngine._result(answer, f"Timetable — {row[1]}", "High", [])


rag_engine = OfflineRAGEngine()
