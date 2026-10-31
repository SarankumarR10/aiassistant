"""Confirmed GUI actions shared by the faculty and student voice consoles."""
from __future__ import annotations

import os
from threading import Event

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QVBoxLayout,
)

from storage.local_storage import storage_service
from voice.local_search import search_local_items
from voice.commands import find_course_materials


class _LocalSearchWorker(QThread):
    results_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, query: str, kind: str, stop_event: Event, parent=None):
        super().__init__(parent)
        self.query = query
        self.kind = kind
        self.stop_event = stop_event

    def run(self):
        try:
            self.results_ready.emit(search_local_items(
                self.query, self.kind, stop_event=self.stop_event,
            ))
        except Exception as error:
            self.failed.emit(str(error))


class LocalSearchDialog(QDialog):
    """Show local matches and open only the item the user explicitly selects."""

    def __init__(self, query: str, kind: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search your computer")
        self.setMinimumSize(620, 440)
        self.setModal(True)
        self._stop_event = Event()
        self._result_text = ""
        self._items = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        self.status = QLabel(f"Searching for ‘{query}’…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.results = QListWidget()
        self.results.setAlternatingRowColors(True)
        self.results.itemSelectionChanged.connect(self._update_open_button)
        self.results.itemDoubleClicked.connect(lambda _item: self._open_selected())
        layout.addWidget(self.results, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.open_button = self.buttons.addButton("Open Selected", QDialogButtonBox.AcceptRole)
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.worker = _LocalSearchWorker(query, kind, self._stop_event, self)
        self.worker.results_ready.connect(self._show_results)
        self.worker.failed.connect(self._search_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _show_results(self, results):
        self._items = results
        self.results.clear()
        for result in results:
            item = QListWidgetItem(f"{result['name']}  ·  {result['kind']}\n{result['path']}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            item.setToolTip(result["path"])
            self.results.addItem(item)
        self.status.setText(
            f"Found {len(results)} match{'es' if len(results) != 1 else ''}. "
            "Select one to review and open it. Search covers local folders and installed app shortcuts."
            if results else
            "No matches found. Try a shorter name or search with a file type such as ‘report pdf’."
        )
        if not results:
            self._result_text = "No matching files or apps were found."
        self._update_open_button()

    def _worker_finished(self):
        if self.worker.isRunning():
            return
        if not self._items and "No matches" not in self.status.text():
            self.status.setText("Search could not be completed. Try again with a shorter name.")

    def _search_failed(self, _message):
        self.status.setText("Search could not be completed. Try again with a shorter name.")
        self._result_text = "Search could not be completed."

    def _update_open_button(self):
        self.open_button.setEnabled(bool(self.results.selectedItems()))

    def _open_selected(self):
        selected = self.results.currentItem()
        if selected is None:
            return
        result = selected.data(Qt.ItemDataRole.UserRole)
        kind = result["kind"]
        choice = QMessageBox.question(
            self,
            "Confirm open",
            f"Open this {kind.lower()}?\n\n{result['name']}\n{result['path']}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            self._result_text = "Open cancelled."
            return
        try:
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(result["path"]))
        except Exception:
            opened = False
        if not opened and os.name == "nt":
            try:
                os.startfile(result["path"])
                opened = True
            except OSError:
                opened = False
        if opened:
            self._result_text = f"Opened {result['name']}."
            self.status.setText(self._result_text)
            QTimer.singleShot(600, self.accept)
        else:
            QMessageBox.warning(self, "Could not open item", "No suitable application could open this item.")
            self._result_text = "Could not open the selected item."

    def closeEvent(self, event):
        if self.worker.isRunning():
            self._stop_event.set()
            self.worker.wait(2000)
        super().closeEvent(event)


def search_local_item(parent, query: str, kind: str = "all") -> str:
    dialog = LocalSearchDialog(query, kind, parent)
    dialog.exec()
    return dialog._result_text or "Search closed."


def open_course_material(parent, query: str) -> str:
    matches = find_course_materials(query)
    if not matches:
        return "No matching course notes or manuals were found. Try a subject, title, or unit number."

    choices = [f"{row[1]} — Unit {row[3]} — {row[4]} ({storage_service.file_name(row[5])})" for row in matches]
    if len(choices) == 1:
        selected = choices[0]
    else:
        selected, accepted = QInputDialog.getItem(
            parent, "Choose course material", "Select a matching course document:", choices, 0, False
        )
        if not accepted:
            return "Opening course material cancelled."
    note = matches[choices.index(selected)]
    try:
        path = storage_service.resolve(note[5]).resolve()
        if not path.is_file():
            raise FileNotFoundError("The course file is no longer available on this device.")
    except Exception as error:
        QMessageBox.warning(parent, "Course material unavailable", str(error))
        return f"Could not open {note[4]}: {error}"

    answer = QMessageBox.question(
        parent,
        "Confirm open course material",
        f"Open '{note[4]}' with this computer's default file viewer?",
        QMessageBox.Yes | QMessageBox.Cancel,
        QMessageBox.Cancel,
    )
    if answer != QMessageBox.Yes:
        return "Opening course material cancelled."
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        QMessageBox.warning(parent, "Could not open course material", "No default application could open this file.")
        return "No default application could open this course file."
    return f"Opened {note[4]}."
