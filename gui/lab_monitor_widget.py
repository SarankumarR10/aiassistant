from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QListWidget, QPushButton
)
from PySide6.QtCore import QTimer
from lab.lab_monitor import lab_monitor

class LabMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #0F172A; color: #F8FAFC;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        title = QLabel("Smart Lab Monitoring & System Health")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)

        # Metrics Container Card
        metrics_card = QFrame()
        metrics_card.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
                padding: 15px;
            }
        """)
        metrics_layout = QVBoxLayout(metrics_card)
        metrics_layout.setSpacing(18)

        self.cpu_bar, self.cpu_lbl = self._add_metric_row(metrics_layout, "CPU Utilization", "#3B82F6")
        self.ram_bar, self.ram_lbl = self._add_metric_row(metrics_layout, "RAM Memory Usage", "#10B981")
        self.disk_bar, self.disk_lbl = self._add_metric_row(metrics_layout, "Disk Storage Used", "#8B5CF6")

        layout.addWidget(metrics_card)

        # Running Processes Section
        processes_card = QFrame()
        processes_card.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.45);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 15px;
            }
        """)
        proc_layout = QVBoxLayout(processes_card)

        apps_lbl = QLabel("Running Workstation Tools & Processes")
        apps_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #60A5FA; margin-bottom: 8px;")
        proc_layout.addWidget(apps_lbl)

        self.apps_list = QListWidget()
        self.apps_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(15, 23, 42, 0.6);
                color: #34D399;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 8px;
            }
            QListWidget::item {
                padding: 6px 4px;
            }
        """)
        proc_layout.addWidget(self.apps_list)

        layout.addWidget(processes_card)

        # Refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(2000)

        self.update_metrics()

    def _add_metric_row(self, layout, title: str, accent_color: str):
        row = QVBoxLayout()
        row.setSpacing(6)

        lbl = QLabel(f"{title}: --%")
        lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: #F8FAFC;")

        bar = QProgressBar()
        bar.setMinimumHeight(24)
        bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                text-align: center;
                background-color: rgba(15, 23, 42, 0.8);
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
            }}
            QProgressBar::chunk {{
                background-color: {accent_color};
                border-radius: 6px;
            }}
        """)
        row.addWidget(lbl)
        row.addWidget(bar)
        layout.addLayout(row)
        return bar, lbl

    def update_metrics(self):
        try:
            metrics = lab_monitor.get_system_health()
            
            self.cpu_bar.setValue(int(metrics["cpu_percent"]))
            self.cpu_lbl.setText(f"CPU Utilization: {metrics['cpu_percent']}%")

            self.ram_bar.setValue(int(metrics["ram_percent"]))
            self.ram_lbl.setText(f"RAM Memory Usage: {metrics['ram_percent']}%  [{metrics['ram_used_gb']} GB / {metrics['ram_total_gb']} GB]")

            self.disk_bar.setValue(int(metrics["disk_percent"]))
            self.disk_lbl.setText(f"Disk Storage Used: {metrics['disk_percent']}%  [{metrics['disk_free_gb']} GB Free]")

            self.apps_list.clear()
            for app in metrics["running_apps"]:
                self.apps_list.addItem(f"{app} (Active)")
        except Exception:
            pass
