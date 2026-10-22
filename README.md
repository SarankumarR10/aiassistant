# EduPilot - Classroom & Laboratory Assistant

EduPilot is an offline-first desktop application for faculty and students. It includes attendance, assignments, student records, local course-material search, and lab workflows. The student workspace includes a restricted code runner; faculty no longer see that tool. The app uses **PySide6 (Qt for Python)** and **SQLite**.

The application has database-backed faculty and student workflows. Microphone speech recognition needs a separately installed Vosk model. Face attendance remains disabled until consented enrollment and identity matching are implemented.

EduPilot uses a split data store. PostgreSQL holds shared academic records and accounts when configured; SQLite keeps private device-only data such as voice notes and local application secrets. Without PostgreSQL configured, the app uses SQLite for the whole database. PostgreSQL access is currently a direct connection for a controlled classroom/demo network; do not expose it to the public internet. A production product should put an authenticated API between desktop clients and PostgreSQL. Uploaded files remain local to the device, and offline AI/course-material search stays on the device.

---

## 🚀 Quick Start for Team Members

Install Python 3.10 or newer, then set up and start the project. Run these scripts from the `aiassistant` folder.

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

### Optional offline speech features

The microphone requires the optional packages and a separately downloaded Vosk English model. From the `aiassistant` folder, run `pip install -r requirements-optional.txt`, then place the extracted model in `models/vosk-model-small-en-us-0.15`. Text commands and the rest of the app do not require this setup.

### Optional student code runner

The student code runner needs Docker Desktop or Docker Engine with Linux containers enabled. Build its restricted execution image from the project root:

```bash
docker build -f docker/Dockerfile.runner -t edupilot-runner:latest docker
```

The runner has no network, a read-only base filesystem, a temporary per-run workspace, a 256 MB memory cap, process limit, and execution timeout. If Docker or the image is unavailable, EduPilot reports that code was not run. Do not switch this feature to direct host execution for untrusted programs.

Practical exams open in fullscreen after the student confirms. The app keeps the exam timer running, autosaves a private draft, submits the last answer when time expires, and prevents normal in-app navigation or closing until submission or timeout. This is an app-level exam mode; Windows shortcuts and administrator tools can still switch away or stop the app, so it is not a managed-device kiosk or remote proctoring system.

### Connect to PostgreSQL

Install PostgreSQL, start the server, then run the setup wizard from the project folder:

```powershell
python setup_postgres.py
```

Enter the PostgreSQL `postgres` administrator password when prompted. The wizard creates the `edupilot` database and a limited app login, then saves its connection in the user's EduPilot application-data folder. It does not put credentials in project files. Start the app normally with `run.bat` or `./run.sh`.

Alternatively, set `EDUPILOT_DATABASE_URL` before starting the app to override that saved connection. For example, on Windows PowerShell:

```powershell
$env:EDUPILOT_DATABASE_URL = "postgresql://user:password@localhost:5432/edupilot"
python main.py
```

The app creates its shared tables and demo accounts in PostgreSQL at startup. Personal voice notes and local app secrets stay in SQLite on each device. To run fully from SQLite, remove the saved connection file from the EduPilot application-data folder and unset `EDUPILOT_DATABASE_URL`. PostgreSQL mode is currently for a trusted LAN/demo; remote multi-device deployment needs an API service, TLS, and shared file storage.

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

`requirements.txt` installs the core desktop app and its supported features: PySide6, QR image creation, Excel exports, PDF text extraction, and workstation metrics. `requirements-optional.txt` is only for local speech recognition, speech output, and camera-based tools. The Vosk model and Docker runner image are separate downloads; neither is bundled with the source.

### Data and file storage

Shared academic records are stored in PostgreSQL when configured. Private voice notes and local application secrets are stored in the per-device SQLite file. Uploaded course documents and assignment attachments are copied into a private, per-user application data folder; the database stores file keys and metadata rather than file contents. Uploads are limited to 25 MB and an extension allowlist. Existing SQLite databases in the older project `database/edupilot.db` location are copied to the new user data location on first launch, preserving their contents.

Default data locations:

| System | Application data folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\EduPilot` |
| macOS | `~/Library/Application Support/EduPilot` |
| Linux | `$XDG_DATA_HOME/edupilot` or `~/.local/share/edupilot` |

Optional environment variables:

| Variable | Purpose |
| --- | --- |
| `EDUPILOT_DATA_DIR` | Override the per-user data folder (database and default file folder) |
| `EDUPILOT_DB_PATH` | Use a specific SQLite database file |
| `EDUPILOT_DATABASE_URL` | Configure PostgreSQL for shared academic records |
| `EDUPILOT_FILES_DIR` | Store uploaded files in a separate local folder |

There are no required secrets or cloud credentials. Back up the SQLite file and its sibling `files` folder together. A cloud/S3-compatible provider is appropriate only if a future deployment needs shared, multi-device access; signed URLs and remote storage are not implemented in this offline desktop build.

### Run core workflow checks

From the project folder, run `python -m unittest discover -s tests -v`. These tests cover database initialization and legacy database migration, hashed login, QR attendance, course-document retrieval, and managed assignment attachments. They use temporary databases and files.

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
