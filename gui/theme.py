"""Shared, restrained EduPilot interface theme."""

from PySide6.QtWidgets import (
    QLabel, QFrame, QHBoxLayout, QWidget, QVBoxLayout, QScrollArea, QLayout,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics, QPalette
import os

COLOR_PRIMARY = "#263746"
COLOR_SECONDARY = "#48677D"
COLOR_ACCENT = COLOR_SECONDARY
COLOR_SUCCESS = "#48677D"
COLOR_WARNING = "#7A6B52"
COLOR_ERROR = "#7A5555"
COLOR_NEUTRAL_BG = "#F4F6F8"
COLOR_SURFACE = "#FFFFFF"
COLOR_BORDER = "#DCE2E7"
COLOR_BORDER_FOCUS = COLOR_SECONDARY
COLOR_TEXT_MAIN = "#26323B"
COLOR_TEXT_MUTED = "#687782"


def install_app_fonts(application) -> None:
    """Register Windows' installed UI font so Qt offscreen/packaged builds can resolve glyphs."""
    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"):
        path = os.path.join(fonts_dir, filename)
        if os.path.isfile(path):
            QFontDatabase.addApplicationFont(path)
    families = QFontDatabase.families()
    family = "Segoe UI" if "Segoe UI" in families else QFontDatabase.systemFont(QFontDatabase.GeneralFont).family()
    application.setFont(QFont(family, 10))


def style_action_button(button: QWidget, variant: str = "primary") -> None:
    """Apply readable button colors directly so dynamically styled Qt buttons stay legible."""
    if variant == "outline":
        button.setStyleSheet("QPushButton { background: #FFFFFF; color: #354E60; border: 1px solid #C8D1D7; border-radius: 7px; padding: 8px 14px; font-weight: 600; } QPushButton:hover { background: #EEF2F4; }")
    elif variant == "muted":
        button.setStyleSheet("QPushButton { background: #EEF1F3; color: #26323B; border: 1px solid #DCE2E7; border-radius: 7px; padding: 8px 14px; font-weight: 600; } QPushButton:hover { background: #E5E9EC; }")
    else:
        button.setStyleSheet("QPushButton { background: #354E60; color: #FFFFFF; border: 1px solid #354E60; border-radius: 7px; padding: 8px 14px; font-weight: 600; } QPushButton:hover { background: #48677D; }")

POSITIVUS_QSS = """
QWidget {
    background-color: #F4F6F8;
    color: #26323B;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}
QLabel { color: #26323B; background: transparent; }
QScrollBar:vertical { background: #EEF1F3; width: 9px; border: none; margin: 2px; }
QScrollBar::handle:vertical { background: #C4CDD4; min-height: 24px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: #9AA8B2; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #EEF1F3; height: 9px; border: none; margin: 2px; }
QScrollBar::handle:horizontal { background: #C4CDD4; min-width: 24px; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QLineEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {
    background: #FFFFFF; color: #26323B; border: 1px solid #D5DDE2;
    border-radius: 7px; padding: 8px 10px; selection-background-color: #48677D;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus,
QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #48677D; }
QLineEdit::placeholder, QTextEdit::placeholder { color: #8A979F; }
QComboBox::drop-down { width: 25px; border-left: 1px solid #E1E6E9; }
QComboBox QAbstractItemView { background: #FFFFFF; color: #26323B; border: 1px solid #D5DDE2; selection-background-color: #E8EEF2; selection-color: #26323B; }
QPushButton {
    background: #354E60; color: #FFFFFF; border: 1px solid #354E60;
    border-radius: 7px; padding: 8px 14px; font-weight: 600;
}
QPushButton:hover { background: #48677D; border-color: #48677D; }
QPushButton:pressed { background: #263746; }
QPushButton:disabled { background: #E5E9EC; color: #98A3AA; border-color: #E5E9EC; }
QPushButton[class="secondary"], QPushButton[class="accent"], QPushButton[class="success"] {
    background: #48677D; color: #FFFFFF; border: 1px solid #48677D;
}
QPushButton[class="secondary"]:hover, QPushButton[class="accent"]:hover,
QPushButton[class="success"]:hover { background: #354E60; }
QPushButton[class="danger"] { background: #FFFFFF; color: #765454; border: 1px solid #D8CACA; }
QPushButton[class="danger"]:hover { background: #F5EEEE; }
QPushButton[class="outline"] { background: #FFFFFF; color: #354E60; border: 1px solid #C8D1D7; }
QPushButton[class="outline"]:hover { background: #EEF2F4; border-color: #9AAAB4; }
QTableWidget, QTreeWidget, QListWidget {
    background: #FFFFFF; color: #26323B; border: 1px solid #DCE2E7;
    border-radius: 8px; gridline-color: #EDF0F2; outline: 0;
}
QTableWidget::item, QListWidget::item { padding: 8px 10px; border-bottom: 1px solid #EEF1F3; }
QTableWidget::item:selected, QListWidget::item:selected { background: #E9EFF3; color: #263746; }
QHeaderView::section { background: #F2F4F6; color: #56656F; padding: 9px 10px; font-weight: 600; border: none; border-bottom: 1px solid #DCE2E7; }
QTabWidget::pane { border: 1px solid #DCE2E7; background: #FFFFFF; border-radius: 8px; }
QTabBar::tab { background: #F2F4F6; color: #687782; border: 1px solid #DCE2E7; padding: 8px 14px; margin-right: 3px; }
QTabBar::tab:selected { background: #FFFFFF; color: #354E60; border-bottom: 2px solid #48677D; }
QProgressBar { border: 1px solid #DCE2E7; border-radius: 5px; background: #EEF1F3; text-align: center; color: #26323B; height: 16px; }
QProgressBar::chunk { background: #718A9A; border-radius: 4px; }
QToolTip { background: #263746; color: #FFFFFF; border: 1px solid #526674; padding: 5px 8px; }
"""


def create_content_scroll_area(content: QWidget) -> QScrollArea:
    """Keep module content reachable in shorter windows and at high DPI."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    area.setStyleSheet("QScrollArea { background: #F4F6F8; border: none; }")
    if content.layout():
        content.layout().setSizeConstraint(QLayout.SetMinimumSize)
    content.setMinimumHeight(content.sizeHint().height())
    area.setWidget(content)
    return area


class _WrappedListDelegate(QStyledItemDelegate):
    """Give multi-line list entries enough height and paint them without eliding."""

    def sizeHint(self, option, index):
        width = option.rect.width()
        if width <= 0 and option.widget:
            width = option.widget.viewport().width()
        width = max(180, width)
        text = str(index.data(Qt.DisplayRole) or "")
        bounds = QFontMetrics(option.font).boundingRect(
            QRect(0, 0, width - 24, 10000), Qt.TextWordWrap, text
        )
        return QSize(width, max(42, bounds.height() + 20))

    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        text = str(index.data(Qt.DisplayRole) or "")
        styled.text = ""
        if styled.widget:
            styled.widget.style().drawControl(
                QStyle.CE_ItemViewItem, styled, painter, styled.widget
            )
        color_role = (
            QPalette.ColorRole.HighlightedText
            if styled.state & QStyle.State_Selected
            else QPalette.ColorRole.Text
        )
        painter.save()
        painter.setPen(styled.palette.color(color_role))
        text_rect = styled.rect.adjusted(10, 7, -10, -7)
        painter.drawText(text_rect, Qt.TextWordWrap | Qt.AlignVCenter, text)
        painter.restore()


def configure_wrapped_list(widget: QWidget) -> None:
    """Make long list descriptions readable instead of clipped to one row."""
    widget.setWordWrap(True)
    widget.setTextElideMode(Qt.ElideNone)
    widget.setUniformItemSizes(False)
    widget.setItemDelegate(_WrappedListDelegate(widget))


def create_pill_badge(
    text: str, bg_color: str = "#E9EEF1", text_color: str = "#354E60", font_size: int = 11
) -> QLabel:
    badge = QLabel(f" {text.upper()} ")
    badge.setStyleSheet(
        f"background: {bg_color}; color: {text_color}; border: 1px solid #D5DDE2; "
        f"border-radius: 5px; padding: 4px 9px; font-size: {font_size}px; font-weight: 600;"
    )
    return badge


def create_section_header(title: str, subtitle: str = "") -> QWidget:
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    title_label = QLabel(title)
    title_label.setStyleSheet("color: #26323B; font-size: 21px; font-weight: 700;")
    layout.addWidget(title_label)
    if subtitle:
        sub_label = QLabel(subtitle)
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet("color: #687782; font-size: 13px;")
        layout.addWidget(sub_label)
    return container
