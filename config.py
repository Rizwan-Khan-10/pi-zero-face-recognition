"""
All settings, paths and environment variables live here.
Every other module imports from config instead of hardcoding paths.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)  # keep every relative path anchored to the project folder
load_dotenv()

# ---------------- camera / stream ----------------
# In .env you can set STREAM_URL to the Pi's URL, or "0" to use a laptop webcam for testing.
_src = os.getenv("STREAM_URL", "http://attendance-pi.local:5000/video_feed").strip()
STREAM_URL = int(_src) if _src.isdigit() else _src

# ---------------- file locations ----------------
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODEL_FILE = os.path.join(BASE_DIR, "trainer.yml")
LABELS_FILE = os.path.join(BASE_DIR, "labels.json")
ATTENDANCE_DIR = os.path.join(BASE_DIR, "attendance")
BRANCHES_FILE = os.path.join(BASE_DIR, "branches.json")
SUBJECTS_FILE = os.path.join(BASE_DIR, "subjects.json")
CASCADE_FILE = os.path.join(BASE_DIR, "haarcascade_frontalface_default.xml")

# ---------------- app settings ----------------
SAMPLES_PER_STUDENT = 25
CAPTURE_INTERVAL = 0.2          # seconds between two saved samples
CONFIDENCE_THRESHOLD = 65
COLLEGE_EMAIL_DOMAIN = "mhssce.ac.in"
VIDEO_W, VIDEO_H = 480, 360
SEMESTERS = [str(i) for i in range(1, 9)]   # every branch always has semesters 1-8
DEFAULT_SEMESTER = "7"                      # pre-selected everywhere (Attendance, Report, Subjects ...)
DEFAULT_BRANCHES = ["IT"]                    # only IT for now - add more in Manage Branches

# ---------------- email settings (from .env) ----------------
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").strip().lower() in ("true", "1", "yes")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "").strip()
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD", "").replace(" ", "").strip().strip('"').strip("'")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

ATTENDANCE_ELIGIBILITY_THRESHOLD = 75   # % - DEFAULT minimum; below this shows red in the Report.
                                        # It can be changed live from the Report screen (box top-right).

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(ATTENDANCE_DIR, exist_ok=True)
