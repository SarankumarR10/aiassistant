"""Combined faculty online exam creation and submission review workspace."""
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from gui.online_exam_review_widget import OnlineExamReviewWidget
from gui.online_exam_widget import OnlineExamBuilderWidget


class OnlineExamManagementWidget(QWidget):
    def __init__(self, faculty_id: int):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.builder = OnlineExamBuilderWidget(faculty_id)
        self.review = OnlineExamReviewWidget(faculty_id)
        self.tabs.addTab(self.builder, "Create and Manage Exams")
        self.tabs.addTab(self.review, "Submitted Answers and Marks")
        self.tabs.currentChanged.connect(self._refresh_review)
        layout.addWidget(self.tabs)

    def _refresh_review(self, index: int):
        if index == 1:
            self.review.refresh_exams()
