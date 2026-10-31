"""Microphone selection and live input-level feedback for voice screens."""
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QProgressBar, QWidget

from voice.speech_input import list_input_devices


class MicrophoneSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("EduPilot", "EduPilot")
        self.devices = list_input_devices()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Microphone:"))

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(220)
        self.device_combo.addItem("System Default", None)
        for device in self.devices:
            suffix = " (Default)" if device["default"] else ""
            self.device_combo.addItem(f"{device['name']}{suffix}", device["id"])
        saved_name = self.settings.value("voice/microphone_name", "")
        if saved_name:
            for index, device in enumerate(self.devices, start=1):
                if device["name"] == saved_name:
                    self.device_combo.setCurrentIndex(index)
                    break
        self.device_combo.currentIndexChanged.connect(self._save_selection)
        layout.addWidget(self.device_combo)

        level_label = QLabel("Input level")
        layout.addWidget(level_label)
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(True)
        self.level_bar.setFormat("%p%")
        self.level_bar.setMaximumWidth(150)
        self.level_bar.setAccessibleName("Microphone input level")
        layout.addWidget(self.level_bar)
        layout.addStretch(1)

        self.setToolTip("Speak at your normal volume while listening. The bar confirms the selected microphone is receiving audio.")

    @property
    def selected_device(self) -> int | None:
        value = self.device_combo.currentData()
        return int(value) if value is not None else None

    def set_level(self, value: int):
        self.level_bar.setValue(max(0, min(100, int(value))))

    def _save_selection(self, index: int):
        device_id = self.device_combo.itemData(index)
        name = next((device["name"] for device in self.devices if device["id"] == device_id), "")
        self.settings.setValue("voice/microphone_name", name)
