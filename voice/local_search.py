"""Bounded local file and application search for voice assistant requests."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


_SKIP_DIRECTORY_NAMES = {
    "$recycle.bin", "system volume information", "windows", "windowsapps",
    "program files", "program files (x86)", "programdata", "appdata",
    ".git", ".venv", "venv", "node_modules", "__pycache__", "temp", "tmp",
}
_APP_EXTENSIONS = {".exe", ".lnk", ".app", ".desktop"}


def _matches(name: str, query_words: list[str]) -> bool:
    normalized = " ".join(Path(name).name.casefold().replace("_", " ").replace("-", " ").replace(".", " ").split())
    return bool(normalized) and all(word in normalized for word in query_words)


def _file_roots() -> list[Path]:
    roots = []
    home = Path.home()
    for folder in ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "OneDrive"):
        candidate = home / folder
        if candidate.is_dir():
            roots.append(candidate)
    project = Path(__file__).resolve().parents[1]
    roots.append(project)

    # Include available Windows drives so a requested file need not be in the
    # current project. System and package-cache directories are pruned below.
    if os.name == "nt":
        try:
            import ctypes
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            for index in range(26):
                if mask & (1 << index):
                    drive = Path(f"{chr(65 + index)}:\\")
                    # Skip network and optical drives so a disconnected mount
                    # cannot stall a local voice search.
                    if ctypes.windll.kernel32.GetDriveTypeW(str(drive)) == 3 and drive.is_dir():
                        roots.append(drive)
        except Exception:
            pass
    unique = {}
    for root in roots:
        try:
            unique[str(root.resolve()).casefold()] = root.resolve()
        except OSError:
            continue
    return list(unique.values())


def _app_roots() -> list[Path]:
    roots = []
    for variable in ("APPDATA", "PROGRAMDATA"):
        base = os.environ.get(variable)
        if base:
            roots.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [path for path in roots if path.is_dir()]


def search_local_items(query: str, kind: str = "all", *, stop_event=None,
                       max_results: int = 80, max_entries: int = 200_000,
                       time_limit: float = 25.0) -> list[dict]:
    """Search personal/local folders or installed-app shortcuts by display name."""
    words = [word.casefold() for word in query.split() if word.strip()]
    if not words:
        return []
    if kind not in {"all", "files", "apps"}:
        raise ValueError("Search type must be files, apps, or all.")

    results = []
    seen = set()

    def add(path: Path, item_kind: str):
        try:
            resolved = str(path.resolve()).casefold()
        except OSError:
            resolved = str(path).casefold()
        if resolved in seen:
            return
        seen.add(resolved)
        results.append({"name": path.stem, "path": str(path), "kind": item_kind})

    if kind in {"all", "apps"}:
        for root in _app_roots():
            for current, dirs, files in os.walk(root, onerror=lambda _error: None):
                if stop_event and stop_event.is_set():
                    return results
                dirs[:] = [name for name in dirs if name.casefold() not in _SKIP_DIRECTORY_NAMES]
                for name in files:
                    if stop_event and stop_event.is_set():
                        return results
                    path = Path(current) / name
                    if path.suffix.casefold() in _APP_EXTENSIONS and _matches(name, words):
                        add(path, "App")
                        if len(results) >= max_results:
                            return results
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            if not directory:
                continue
            try:
                entries = Path(directory).iterdir()
                for path in entries:
                    if path.is_file() and path.suffix.casefold() in _APP_EXTENSIONS and _matches(path.name, words):
                        add(path, "App")
                        if len(results) >= max_results:
                            return results
            except (OSError, PermissionError):
                continue

    if kind in {"all", "files"} and len(results) < max_results:
        started = time.monotonic()
        visited = 0
        for root in _file_roots():
            for current, dirs, files in os.walk(root, onerror=lambda _error: None):
                if (stop_event and stop_event.is_set()) or visited >= max_entries \
                        or time.monotonic() - started >= time_limit:
                    return results
                dirs[:] = [name for name in dirs if name.casefold() not in _SKIP_DIRECTORY_NAMES]
                for name in files:
                    if stop_event and stop_event.is_set():
                        return results
                    visited += 1
                    if _matches(name, words):
                        add(Path(current) / name, "File")
                        if len(results) >= max_results:
                            return results
                    if visited >= max_entries or time.monotonic() - started >= time_limit:
                        return results
    return results
