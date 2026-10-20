"""
Face Recognition Attendance System - Desktop GUI

Install:
    pip install -r requirements.txt

Run (from this folder):
    python app.py
"""

import config  # noqa: F401  (sets BASE_DIR, chdir, loads .env - must run first)
from ui.main_window import App

if __name__ == "__main__":
    app = App()
    app.mainloop()
