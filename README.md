# EduPilot - Classroom & Laboratory Assistant

EduPilot is a desktop AI personal assistant for classroom management, attendance tracking, laboratory monitoring, code execution, student progress analytics, and voice-assisted studying built with **PySide6 (Qt for Python)** and **SQLite**.

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
* **`opencv-python`**: Face detection and anti-proxy attendance feature.
* **`numpy`**: Image processing & array mathematics.
* **`pyttsx3`**: Offline Text-to-Speech (TTS) engine.
* **`vosk`**: Offline Speech Recognition engine.
* **`requests`**: HTTP library for fetching external resources.
* **`tqdm`**, **`colorama`**: CLI utility formatting & progress indicators.

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
├── reports/                 # CSV and HTML report export generators
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
