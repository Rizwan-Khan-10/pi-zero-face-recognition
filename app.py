"""
Face Recognition Attendance System - Desktop GUI (Tkinter)

Install first:
    pip install pillow

Uses the same dataset/, labels.json, trainer.yml, attendance/ files as the
old register_student.py / mark_attendance.py scripts - fully compatible
with students you already registered.

Run:
    python app.py
"""

import cv2
import os
import json
import csv
import threading
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from PIL import Image, ImageTk

STREAM_URL = "http://attendance-pi.local:5000/video_feed"
DATASET_DIR = "dataset"
MODEL_FILE = "trainer.yml"
LABELS_FILE = "labels.json"
ATTENDANCE_DIR = "attendance"
SAMPLES_PER_STUDENT = 25
CONFIDENCE_THRESHOLD = 65

face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(ATTENDANCE_DIR, exist_ok=True)


# ---------- shared helpers (same logic as before) ----------

def load_labels():
    if os.path.exists(LABELS_FILE):
        with open(LABELS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_labels(labels):
    with open(LABELS_FILE, "w") as f:
        json.dump(labels, f)


def train_model():
    labels = load_labels()
    faces, label_ids = [], []

    for folder_name in os.listdir(DATASET_DIR):
        parts = folder_name.split("_", 1)
        roll_no = parts[0]
        if roll_no not in labels:
            labels[roll_no] = {"label_id": len(labels), "name": parts[1] if len(parts) > 1 else ""}
        label_id = labels[roll_no]["label_id"]
        folder_path = os.path.join(DATASET_DIR, folder_name)
        for img_name in os.listdir(folder_path):
            img = cv2.imread(os.path.join(folder_path, img_name), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                faces.append(img)
                label_ids.append(label_id)

    save_labels(labels)
    if faces:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(faces, np.array(label_ids))
        recognizer.save(MODEL_FILE)


def get_today_file():
    return os.path.join(ATTENDANCE_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.csv")


def load_marked_today():
    path = get_today_file()
    marked = set()
    if os.path.exists(path):
        with open(path, "r") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                marked.add(row[0])
    return marked


def mark_present(roll_no, name):
    path = get_today_file()
    is_new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["roll_no", "name", "time", "status"])
        writer.writerow([roll_no, name, datetime.now().strftime("%H:%M:%S"), "Present"])


def mark_absent(roll_no, name):
    path = get_today_file()
    is_new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["roll_no", "name", "time", "status"])
        writer.writerow([roll_no, name, "-", "Absent"])


def finalize_absentees():
    """Mark every registered student not already in today's CSV as Absent."""
    labels = load_labels()
    marked = load_marked_today()
    count = 0
    for roll_no, info in labels.items():
        if roll_no not in marked:
            mark_absent(roll_no, info.get("name", ""))
            count += 1
    return count


# ---------- background camera reader (avoids GUI freezing) ----------

class CameraStream:
    def __init__(self, url):
        self.url = url
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def start(self):
        self.cap = cv2.VideoCapture(self.url)
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        while self.running:
            if self.cap is None:
                break
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def get_frame(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.cap:
            self.cap.release()
        self.cap = None
        self.frame = None


# ---------- GUI screens ----------

class HomeScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        ttk.Label(self, text="Attendance System", font=("Segoe UI", 20, "bold")).pack(pady=40)
        ttk.Button(self, text="Add Student", width=25,
                   command=lambda: controller.show("AddStudentScreen")).pack(pady=10)
        ttk.Button(self, text="Start Attendance", width=25,
                   command=lambda: controller.show("AttendanceScreen")).pack(pady=10)
        ttk.Button(self, text="View Report", width=25,
                   command=lambda: controller.show("ReportScreen")).pack(pady=10)


class AddStudentScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.camera = None
        self.active = False
        self.capturing = False
        self.count = 0
        self.folder = None

        top = ttk.Frame(self)
        top.pack(pady=10)
        ttk.Label(top, text="Name:").grid(row=0, column=0, padx=5, pady=5)
        self.name_entry = ttk.Entry(top, width=25)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(top, text="Roll No:").grid(row=1, column=0, padx=5, pady=5)
        self.roll_entry = ttk.Entry(top, width=25)
        self.roll_entry.grid(row=1, column=1, padx=5, pady=5)

        self.video_label = ttk.Label(self, text="Camera preview will appear here",
                                      background="black", foreground="white", width=60)
        self.video_label.pack(pady=10)

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack()

        btns = ttk.Frame(self)
        btns.pack(pady=10)
        self.start_btn = ttk.Button(btns, text="Start Capturing", command=self.start_capturing)
        self.start_btn.grid(row=0, column=0, padx=5)
        ttk.Button(btns, text="Back", command=lambda: controller.show("HomeScreen")).grid(row=0, column=1, padx=5)

    def start_capturing(self):
        name = self.name_entry.get().strip()
        roll_no = self.roll_entry.get().strip()
        if not name or not roll_no:
            messagebox.showwarning("Missing info", "Please enter both name and roll number.")
            return

        self.folder = os.path.join(DATASET_DIR, f"{roll_no}_{name}")
        os.makedirs(self.folder, exist_ok=True)
        self.count = 0
        self.capturing = True
        self.active = True
        self.start_btn.config(state="disabled")
        self.name_entry.config(state="disabled")
        self.roll_entry.config(state="disabled")
        self.status_label.config(text=f"Capturing 0/{SAMPLES_PER_STUDENT}...")

        self.camera = CameraStream(STREAM_URL)
        self.camera.start()
        self.update_frame()

    def update_frame(self):
        if not self.active:
            return
        frame = self.camera.get_frame()
        if frame is not None:
            display = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
                if self.capturing and self.count < SAMPLES_PER_STUDENT:
                    face_img = cv2.resize(gray[y:y + h, x:x + w], (200, 200))
                    self.count += 1
                    cv2.imwrite(os.path.join(self.folder, f"{self.count}.jpg"), face_img)
                    self.status_label.config(text=f"Capturing {self.count}/{SAMPLES_PER_STUDENT}...")

            self.show_frame(display)

            if self.capturing and self.count >= SAMPLES_PER_STUDENT:
                self.finish_capturing()
                return

        self.after(30, self.update_frame)

    def show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb).resize((480, 360))
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.config(image=imgtk)

    def finish_capturing(self):
        self.active = False
        self.capturing = False
        self.camera.stop()
        self.camera = None
        train_model()
        self.status_label.config(text=f"Registered successfully with {self.count} samples!")
        self.start_btn.config(state="normal")
        self.name_entry.config(state="normal")
        self.roll_entry.config(state="normal")
        self.name_entry.delete(0, tk.END)
        self.roll_entry.delete(0, tk.END)

    def on_leave(self):
        self.active = False
        self.capturing = False
        if self.camera:
            self.camera.stop()
            self.camera = None


class AttendanceScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.camera = None
        self.running = False
        self.marked_today = set()
        self.recognizer = None
        self.id_to_student = {}

        self.video_label = ttk.Label(self, text="Camera preview will appear here",
                                      background="black", foreground="white", width=60)
        self.video_label.pack(pady=10)

        btns = ttk.Frame(self)
        btns.pack(pady=5)
        self.start_btn = ttk.Button(btns, text="Start", command=self.start_attendance)
        self.start_btn.grid(row=0, column=0, padx=5)
        self.stop_btn = ttk.Button(btns, text="Stop", command=self.stop_attendance, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=5)
        ttk.Button(btns, text="Back", command=self.go_back).grid(row=0, column=2, padx=5)

        ttk.Button(self, text="Finalize Day (Mark Absentees)",
                   command=self.finalize_day).pack(pady=(10, 0))

        ttk.Label(self, text="Marked present today:").pack(pady=(15, 0))
        self.listbox = tk.Listbox(self, width=50, height=8)
        self.listbox.pack(pady=5)

    def start_attendance(self):
        if not os.path.exists(MODEL_FILE) or not os.path.exists(LABELS_FILE):
            messagebox.showerror("No model", "No registered students found. Add a student first.")
            return

        labels = load_labels()
        self.id_to_student = {v["label_id"]: (roll_no, v["name"]) for roll_no, v in labels.items()}
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.recognizer.read(MODEL_FILE)
        self.marked_today = load_marked_today()

        self.camera = CameraStream(STREAM_URL)
        self.camera.start()
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.update_frame()

    def update_frame(self):
        if not self.running:
            return
        frame = self.camera.get_frame()
        if frame is not None:
            display = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                face_img = cv2.resize(gray[y:y + h, x:x + w], (200, 200))
                label_id, confidence = self.recognizer.predict(face_img)
                name, color = "Unknown", (0, 0, 255)

                if confidence < CONFIDENCE_THRESHOLD and label_id in self.id_to_student:
                    roll_no, name = self.id_to_student[label_id]
                    color = (0, 255, 0)
                    if roll_no not in self.marked_today:
                        mark_present(roll_no, name)
                        self.marked_today.add(roll_no)
                        self.listbox.insert(0, f"{name} ({roll_no}) - {datetime.now().strftime('%H:%M:%S')}")

                cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
                cv2.putText(display, name, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            self.show_frame(display)

        self.after(30, self.update_frame)

    def show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb).resize((480, 360))
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.config(image=imgtk)

    def stop_attendance(self):
        self.running = False
        if self.camera:
            self.camera.stop()
            self.camera = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def go_back(self):
        self.stop_attendance()
        self.controller.show("HomeScreen")

    def finalize_day(self):
        if not os.path.exists(LABELS_FILE):
            messagebox.showwarning("No students", "No registered students found.")
            return

        confirm = messagebox.askyesno(
            "Finalize attendance?",
            "This will mark every registered student who wasn't scanned today "
            "as Absent, and lock in today's record. Continue?"
        )
        if not confirm:
            return

        self.stop_attendance()
        count = finalize_absentees()
        messagebox.showinfo("Done", f"Day finalized. {count} student(s) marked absent.")

    def on_leave(self):
        self.stop_attendance()


class ReportScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        top = ttk.Frame(self)
        top.pack(pady=10)
        ttk.Label(top, text="Select date:").grid(row=0, column=0, padx=5)
        self.date_combo = ttk.Combobox(top, width=20, state="readonly")
        self.date_combo.grid(row=0, column=1, padx=5)
        self.date_combo.bind("<<ComboboxSelected>>", self.load_table)
        ttk.Button(top, text="Refresh", command=self.refresh_dates).grid(row=0, column=2, padx=5)
        ttk.Button(top, text="Back", command=lambda: controller.show("HomeScreen")).grid(row=0, column=3, padx=5)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(table_frame, columns=("roll", "name", "time", "status"), show="headings")
        widths = {"roll": 90, "name": 160, "time": 100, "status": 90}
        for col, label in zip(("roll", "name", "time", "status"), ("Roll No", "Name", "Time", "Status")):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=widths[col], anchor="center", stretch=False)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

    def refresh_dates(self):
        files = sorted(os.listdir(ATTENDANCE_DIR), reverse=True)
        dates = [f.replace(".csv", "") for f in files if f.endswith(".csv")]
        self.date_combo["values"] = dates
        if dates:
            self.date_combo.set(dates[0])
            self.load_table()

    def load_table(self, event=None):
        for row in self.tree.get_children():
            self.tree.delete(row)
        date = self.date_combo.get()
        if not date:
            return
        path = os.path.join(ATTENDANCE_DIR, f"{date}.csv")
        if os.path.exists(path):
            with open(path, "r") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    self.tree.insert("", "end", values=row)

    def on_leave(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Face Recognition Attendance System")
        self.geometry("560x600")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}
        for ScreenClass in (HomeScreen, AddStudentScreen, AttendanceScreen, ReportScreen):
            frame = ScreenClass(container, self)
            self.frames[ScreenClass.__name__] = frame
            frame.place(relwidth=1, relheight=1)

        self.current = "HomeScreen"
        self.show("HomeScreen")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show(self, name):
        current_frame = self.frames[self.current]
        if hasattr(current_frame, "on_leave"):
            current_frame.on_leave()
        if name == "ReportScreen":
            self.frames[name].refresh_dates()
        self.frames[name].tkraise()
        self.current = name

    def on_close(self):
        for frame in self.frames.values():
            if hasattr(frame, "on_leave"):
                frame.on_leave()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()