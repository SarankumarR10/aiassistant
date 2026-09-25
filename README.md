# EduPilot - Classroom & Laboratory Assistant

EduPilot is a desktop AI personal assistant for classroom management, attendance tracking, laboratory monitoring, code execution, student progress analytics, and voice-assisted studying built with **PySide6 (Qt for Python)** and **SQLite**.

The application has database-backed faculty and student workflows. Microphone speech recognition needs a separately installed Vosk model. Face attendance remains disabled until consented enrollment and identity matching are implemented.

---

## 🚀 Quick Start for Team Members

You can set up and start the project in **one click** on Windows, macOS, or Linux.

### Option 1: One-Click Automated Setup (Recommended)

#### On Windows:
1. Open the project folder (`aiassistant`).
2. Double-click **`setup.bat`** (or run `.\setup.bat` in PowerShell / CMD).
3. Once setup completes, double-click **`run.bat`** (or run `.\run.bat`) to launch EduPilot.

#### On macOS / Linux:
1. Open terminal in the `aiassistant` directory.
2. Run `chmod +x setup.sh run.sh`
3. Run `./setup.sh`
4. Run `./run.sh` to launch EduPilot.

If an existing virtual environment stops working after Python is moved or upgraded, run the setup script again. It checks `venv` first and rebuilds it when its base Python is no longer available.

---

### Option 2: Manual Setup Step-by-Step

If you prefer to set up manually using Python commands:

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate the virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# macOS/Linux:
source venv/bin/activate

# 3. Upgrade pip
python -m pip install --upgrade pip

# 4. Install all package dependencies
pip install -r requirements.txt

# 5. Run EduPilot
python main.py
```

### Isolated code runner (optional)

Install Docker Desktop or Docker Engine with Linux containers enabled, then build the restricted execution image from the project root:

```bash
docker build -f docker/Dockerfile.runner -t edupilot-runner:latest docker
```

The runner has no network, a read-only base filesystem, a temporary per-run workspace, a 256 MB memory cap, process limit, and execution timeout. If Docker or the image is unavailable, EduPilot reports that code was not run. Do not switch this feature to direct host execution for untrusted programs.

---

## 🔑 Default Login Credentials

The project comes pre-seeded with test accounts for Faculty and Student roles:

| Role | Username | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Faculty** | `faculty` | `faculty123` | Full Admin Dashboard, Attendance Taker, Analytics, Lab Exam Control, Question Bank, Notices |
| **Student** | `student` | `student123` | Student Dashboard, Personal Academics, Attendance Report, Code Runner, AI Tutor |
| **Student 2** | `student2` | `student123` | Student View for Bala Kumar |
| **Student 3** | `student3` | `student123` | Student View for Dinesh Raj |

---

## 📦 Installed Packages & Dependencies

All dependencies are defined in `requirements.txt`:
* **`PySide6`**: Modern Qt UI desktop framework.
* **`opencv-python`**: Optional face detection only; detection is not identity verification.
* **`numpy`**: Image processing & array mathematics.
* **`pyttsx3`**: Offline Text-to-Speech (TTS) engine.
* **`vosk`**: Speech recognition library; a local Vosk model is not bundled.
* **`sounddevice`**: Optional local microphone capture for offline Vosk transcription.
* **`pypdf`**: Optional text extraction from course PDFs.
* **`psutil`**: Optional live workstation monitoring.
* **`qrcode[pil]`**: Optional QR image rendering; signed text check-ins work without it.
* **`openpyxl`**: Excel exports for attendance and student transcripts.
* **`tqdm`**, **`colorama`**: CLI utility formatting & progress indicators.

### Optional offline speech input

After installing `requirements.txt`, place an English Vosk model at
`models/vosk-model-small-en-us-0.15`, or point `EDUPILOT_VOSK_MODEL` at the extracted model folder.
The microphone controls become available in the faculty and student voice consoles when the model and
audio dependency are detected. EduPilot does not upload audio or transcripts.

---

## 📁 Project Structure

```text
aiassistant/
├── main.py                  # Application entry point
├── setup.bat / setup.sh     # 1-click automated environment setup scripts
├── run.bat / run.sh         # 1-click application launchers
├── requirements.txt         # Complete dependency manifest
├── ai/                      # AI engines (RAG & Tutor)
├── attendance/              # Face & QR attendance modules
├── database/                # SQLite database management & models
├── gui/                     # PySide6 desktop interface components
├── lab/                     # Code execution & laboratory monitor
├── reports/                 # CSV, HTML, PDF, and Excel report exports
├── voice/                   # Offline voice engine & speech commands
└── docs/                    # Feature specifications & documentation
```

---

## ❓ Troubleshooting & Common Issues

#### 1. `ModuleNotFoundError: No module named 'PySide6'` or `No module named 'cv2'`
* **Cause**: Python is using your global interpreter instead of the project virtual environment.
* **Solution**: Ensure your virtual environment is activated before running:
  - Windows: `.\venv\Scripts\activate.bat`
  - Run `pip install -r requirements.txt` again inside the venv.

#### 2. `PySide6 / Qt plugin error`
* **Solution**: Ensure `pip install --upgrade PySide6` was executed inside the virtual environment.

#### 3. Re-initializing or Resetting Data
* To reset the database to factory default test data, delete `edupilot.db` inside the project folder (if generated) and run `python main.py`. The database will auto-rebuild on startup.

#### 4. Existing virtual environment no longer starts
* Run `setup.bat` on Windows or `./setup.sh` on macOS/Linux. The setup script checks the generated `venv` and recreates it if it is incomplete or points to a Python installation that has moved. Then use `run.bat` or `./run.sh` to launch EduPilot with that environment.
