"""Configurable local storage for uploaded EduPilot files.

The database stores a storage key and file metadata. Binary content stays in the
per-user application data directory so database backups remain compact.
"""
from __future__ import annotations

import mimetypes
import os
import uuid
from pathlib import Path

from database.database import APP_DATA_DIR, get_connection


STORAGE_PREFIX = "edupilot-storage://"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg",
    ".docx", ".xlsx", ".zip", ".py", ".c", ".cpp", ".h", ".java",
}


class LocalStorageService:
    """Store files under an app-owned directory with opaque, traversal-safe keys."""

    def __init__(self, root: str | Path | None = None):
        configured = os.environ.get("EDUPILOT_FILES_DIR")
        self.root = Path(root or configured or (APP_DATA_DIR / "files")).expanduser().resolve()

    def store_file(
        self,
        source_path: str | Path,
        *,
        uploaded_by: int | None,
        category: str,
        allowed_extensions: set[str] | None = None,
        max_bytes: int = MAX_UPLOAD_BYTES,
    ) -> str:
        source = Path(source_path).expanduser()
        if not source.is_file():
            raise FileNotFoundError("Choose a file that exists on this computer.")
        extension = source.suffix.lower()
        allowed = allowed_extensions or ALLOWED_EXTENSIONS
        if extension not in allowed:
            raise ValueError(f"Files with the {extension or 'unknown'} extension are not allowed here.")
        size = source.stat().st_size
        if size <= 0:
            raise ValueError("The selected file is empty.")
        if size > max_bytes:
            raise ValueError(f"The selected file exceeds the {max_bytes // (1024 * 1024)} MB limit.")
        if not category.isascii() or not category.replace("_", "").isalnum():
            raise ValueError("Invalid file category.")

        relative_key = Path(category) / f"{uuid.uuid4().hex}{extension}"
        destination = (self.root / relative_key).resolve()
        if not destination.is_relative_to(self.root):
            raise ValueError("Invalid storage destination.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            copied = 0
            with source.open("rb") as incoming, temporary.open("xb") as outgoing:
                while block := incoming.read(1024 * 1024):
                    copied += len(block)
                    if copied > max_bytes:
                        raise ValueError(f"The selected file exceeds the {max_bytes // (1024 * 1024)} MB limit.")
                    outgoing.write(block)
            if copied == 0:
                raise ValueError("The selected file is empty.")
            os.replace(temporary, destination)
            storage_key = relative_key.as_posix()
            media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO stored_files(storage_key, original_name, media_type, size_bytes, uploaded_by) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (storage_key, source.name[:255], media_type, size, uploaded_by),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return STORAGE_PREFIX + storage_key
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

    def resolve(self, reference: str) -> Path:
        if not reference.startswith(STORAGE_PREFIX):
            return Path(reference).expanduser()
        key = reference[len(STORAGE_PREFIX):]
        candidate = (self.root / key).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Invalid stored file reference.")
        return candidate

    def file_name(self, reference: str) -> str:
        if reference.startswith(STORAGE_PREFIX):
            key = reference[len(STORAGE_PREFIX):]
            conn = get_connection()
            try:
                row = conn.execute("SELECT original_name FROM stored_files WHERE storage_key = ?", (key,)).fetchone()
            finally:
                conn.close()
            if row:
                return row[0]
        return self.resolve(reference).name

    def owned_by(self, reference: str, user_id: int) -> bool:
        if not reference.startswith(STORAGE_PREFIX):
            return False
        key = reference[len(STORAGE_PREFIX):]
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM stored_files WHERE storage_key = ? AND uploaded_by = ?",
                (key, user_id),
            ).fetchone()
        finally:
            conn.close()
        return bool(row and self.resolve(reference).is_file())

    def remove(self, reference: str) -> None:
        if not reference.startswith(STORAGE_PREFIX):
            return
        key = reference[len(STORAGE_PREFIX):]
        path = self.resolve(reference)
        conn = get_connection()
        try:
            conn.execute("DELETE FROM stored_files WHERE storage_key = ?", (key,))
            conn.commit()
        finally:
            conn.close()
        path.unlink(missing_ok=True)

    def remove_orphaned_files(self) -> int:
        conn = get_connection()
        try:
            keys = [row[0] for row in conn.execute("""
                SELECT f.storage_key FROM stored_files f
                WHERE NOT EXISTS (SELECT 1 FROM notes n WHERE n.file_path = 'edupilot-storage://' || f.storage_key)
                  AND NOT EXISTS (SELECT 1 FROM documents d WHERE d.file_path = 'edupilot-storage://' || f.storage_key)
                  AND NOT EXISTS (SELECT 1 FROM assignment_submissions s WHERE s.file_path = 'edupilot-storage://' || f.storage_key)
            """).fetchall()]
        finally:
            conn.close()
        for key in keys:
            self.remove(STORAGE_PREFIX + key)
        return len(keys)


storage_service = LocalStorageService()
