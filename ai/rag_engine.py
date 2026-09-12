import os
import re
from database.database import search_faq, get_connection

class OfflineRAGEngine:
    """
    Offline Document Retrieval-Augmented Generation (RAG) Engine.
    Indexes local text / PDF notes and retrieves answers for student queries.
    """
    def __init__(self):
        pass

    def ingest_file(self, title: str, file_path: str, subject_id: int = 1) -> int:
        """Reads PDF or text files and indexes paragraph chunks into SQLite for offline RAG."""
        text_content = ""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            try:
                # Try PyPDF2 / pypdf
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(file_path)
                    for page in reader.pages:
                        text_content += page.extract_text() + "\n"
                except Exception:
                    # Fallback plain text read if pdf is text-formatted or mock
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
            except Exception as e:
                text_content = f"PDF Document: {title}\nUnit contents and reference materials for subject."
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_content = f.read()
            except Exception:
                text_content = f"Document: {title}\nLocal reference material."

        return self.ingest_text_document(title, text_content, subject_id)

    def ingest_text_document(self, title: str, content: str, subject_id: int = 1) -> int:
        """Stores document and creates searchable text chunks in SQLite."""
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO documents (title, subject_id, file_path) VALUES (?, ?, ?)",
                  (title, subject_id, "text_content"))
        doc_id = c.lastrowid

        # Split content into paragraph chunks
        chunks = [ch.strip() for ch in re.split(r'\n\s*\n', content) if len(ch.strip()) > 20]
        if not chunks:
            chunks = [content]

        for idx, chunk in enumerate(chunks):
            c.execute("INSERT INTO document_chunks (document_id, chunk_index, content, keywords) VALUES (?, ?, ?, ?)",
                      (doc_id, idx, chunk, chunk[:100].lower()))
        
        conn.commit()
        conn.close()
        return doc_id

    def query(self, user_question: str) -> dict:

        """
        Searches local FAQs and document chunk database.
        Returns synthesized answer with source citation.
        """
        q = user_question.lower().strip()

        # 1. Search Knowledge Base FAQs
        faqs = search_faq(q)
        if faqs:
            category, question, answer = faqs[0]
            return {
                "answer": answer,
                "source": f"Local FAQ ({category})",
                "confidence": "High"
            }

        # 2. Search Document Chunks
        conn = get_connection()
        c = conn.cursor()
        words = [w for w in re.findall(r'\w+', q) if len(w) > 3]
        
        if not words:
            conn.close()
            return {
                "answer": "Could not understand query. Please specify subject topics like JVM, Normalization, Unit 3, or Process Synchronization.",
                "source": "System",
                "confidence": "Low"
            }

        like_clauses = " OR ".join(["content LIKE ?"] * len(words))
        params = [f"%{w}%" for w in words]

        c.execute(f"""
            SELECT d.title, dc.content
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE {like_clauses}
            LIMIT 3
        """, params)

        rows = c.fetchall()
        conn.close()

        if rows:
            combined = "\n\n".join([f"From '{r[0]}': {r[1]}" for r in rows])
            return {
                "answer": combined,
                "source": rows[0][0],
                "confidence": "Medium"
            }

        # Fallback response with helpful subject breakdown
        return {
            "answer": f"Definition & Explanation for '{user_question}':\nThis topic belongs to core Computer Science syllabus. Review the uploaded lecture slides and unit question bank in the Notes & Manuals tab.",
            "source": "VCET Offline Knowledge Base",
            "confidence": "Standard"
        }

rag_engine = OfflineRAGEngine()
