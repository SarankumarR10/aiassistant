from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QListWidget, QPushButton
)
from PySide6.QtCore import QTimer
from lab.lab_monitor import lab_monitor
from gui.theme import POSITIVUS_QSS, create_section_header

class LabMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(POSITIVUS_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = create_section_header("Lab Monitor & System Health", "Real-time CPU, RAM, Disk & Process tracking")
        layout.addWidget(header)
        self.status_label = QLabel("Connecting to workstation metrics…")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Metrics Container Card
        metrics_card = QFrame()
        metrics_card.setObjectName("surfaceCard")
        metrics_card.setStyleSheet("""
            QFrame#surfaceCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        metrics_layout = QVBoxLayout(metrics_card)
        metrics_layout.setSpacing(16)

        self.cpu_bar, self.cpu_lbl = self._add_metric_row(metrics_layout, "CPU Utilization")
        self.ram_bar, self.ram_lbl = self._add_metric_row(metrics_layout, "RAM Memory Usage")
        self.disk_bar, self.disk_lbl = self._add_metric_row(metrics_layout, "Disk Storage Used")
        self.network_label = QLabel("Network traffic: unavailable")
        self.network_label.setStyleSheet("color: #687782; font-size: 12px;")
        metrics_layout.addWidget(self.network_label)

        layout.addWidget(metrics_card)

        # Running Processes Section
        processes_card = QFrame()
        processes_card.setObjectName("surfaceCard")
        processes_card.setStyleSheet("""
            QFrame#surfaceCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        proc_layout = QVBoxLayout(processes_card)

        apps_lbl = QLabel("Running Workstation Tools & Processes")
        apps_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 6px;")
        proc_layout.addWidget(apps_lbl)

        self.apps_list = QListWidget()
        self.apps_list.setStyleSheet("""
            QListWidget {
                background-color: #F8FAFC;
                color: #0F172A;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        proc_layout.addWidget(self.apps_list)

        layout.addWidget(processes_card)

        # Refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(2000)

        self.update_metrics()

    def _add_metric_row(self, layout, title: str):
        row = QVBoxLayout()
        row.setSpacing(6)

        lbl = QLabel(f"{title}: --%")
        lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #0F172A;")

        bar = QProgressBar()
        bar.setMinimumHeight(20)
        row.addWidget(lbl)
        row.addWidget(bar)
        layout.addLayout(row)
        return bar, lbl

    def update_metrics(self):
        try:
            metrics = lab_monitor.get_system_health()
            if not metrics.get("available", True):
                self.status_label.setText(metrics["status"])
                for bar, label in ((self.cpu_bar, self.cpu_lbl), (self.ram_bar, self.ram_lbl), (self.disk_bar, self.disk_lbl)):
                    bar.setValue(0)
                    label.setText(label.text().split(":")[0] + ": unavailable")
                self.apps_list.clear()
                self.apps_list.addItem("Live process list is unavailable.")
                self.network_label.setText("Network traffic: unavailable")
                return
            self.status_label.setText(f"Live workstation status: {metrics['status']}")
            
            self.cpu_bar.setValue(int(metrics["cpu_percent"]))
            self.cpu_lbl.setText(f"CPU Utilization: {metrics['cpu_percent']}%")

            self.ram_bar.setValue(int(metrics["ram_percent"]))
            self.ram_lbl.setText(f"RAM Memory Usage: {metrics['ram_percent']}%  [{metrics['ram_used_gb']} GB / {metrics['ram_total_gb']} GB]")

            self.disk_bar.setValue(int(metrics["disk_percent"]))
            self.disk_lbl.setText(f"Disk Storage Used: {metrics['disk_percent']}%  [{metrics['disk_free_gb']} GB Free]")
            self.network_label.setText(
                f"Network totals: {metrics['bytes_sent_mb']} MB sent · {metrics['bytes_recv_mb']} MB received"
            )

            self.apps_list.clear()
            for app in metrics["running_apps"]:
                self.apps_list.addItem(f"{app} (Active)")
        except Exception as error:
            self.status_label.setText(f"Could not refresh workstation metrics: {error}")
