import os

class LabMonitorEngine:
    """
    Real-time workstation system monitoring (CPU, RAM, Disk, Network, Running Processes).
    """
    def get_system_health(self) -> dict:
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            net = psutil.net_io_counters()

            running_apps = []
            dev_processes = ["code", "idea64", "eclipse", "studio64", "sqldeveloper", "chrome", "python", "java", "cmd", "powershell"]
            for proc in psutil.process_iter(['name']):
                try:
                    pname = proc.info['name'].lower()
                    for dev in dev_processes:
                        if dev in pname and pname not in running_apps:
                            running_apps.append(pname)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            status = "Healthy"
            if cpu_percent > 85 or memory.percent > 90:
                status = "High Load Warning"

            return {
                "cpu_percent": cpu_percent,
                "ram_percent": memory.percent,
                "ram_used_gb": round(memory.used / (1024**3), 2),
                "ram_total_gb": round(memory.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "bytes_sent_mb": round(net.bytes_sent / (1024**2), 2),
                "bytes_recv_mb": round(net.bytes_recv / (1024**2), 2),
                "running_apps": running_apps,
                "status": status
            }
        except ImportError:
            return {"available": False, "status": "Monitoring unavailable: install psutil to show live workstation metrics."}
        except Exception as e:
            return {"available": False, "status": f"Monitoring unavailable: {e}"}

lab_monitor = LabMonitorEngine()
