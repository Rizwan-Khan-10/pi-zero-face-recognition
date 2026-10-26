"""Add Student screen: form + live camera + automatic face-sample capture."""

import os
import time
import shutil

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
import cv2

import config
from core import storage
from core.camera import CameraStream, camera_message
from core.recognition import face_cascade, train_model, is_sharp_enough
from core.email_service import suggest_email
from ui.widgets import make_header, VideoPanel


class AddStudentScreen(tb.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.camera = None
        self.active = False
        self.capturing = False
        self.count = 0
        self.last_capture = 0
        self.folder = None
        self.folder_new = False
        self.roll_no = self.name = self.branch = self.semester = self.email = None
        self._elective_ids = {}
        self.electives = []

        make_header(self, "Add Student", controller)

        body = tb.Frame(self, padding=20)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")
        body.rowconfigure(0, weight=1)

        # ---- left: form ----
        left = tb.Labelframe(body, text="Student Details", padding=20)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(1, weight=1)

        self.entries = {}
        text_fields = [("Name", "name"), ("Roll No", "roll")]
        for i, (label, key) in enumerate(text_fields):
            tb.Label(left, text=label + ":").grid(row=i, column=0, sticky="w", pady=9)
            entry = tb.Entry(left)
            entry.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=9)
            self.entries[key] = entry

        tb.Label(left, text="Branch:").grid(row=2, column=0, sticky="w", pady=9)
        self.branch_combo = ttk.Combobox(left, state="readonly", values=storage.load_branches())
        self.branch_combo.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=9)
        self.entries["branch"] = self.branch_combo

        tb.Label(left, text="Semester:").grid(row=3, column=0, sticky="w", pady=9)
        self.semester_combo = ttk.Combobox(left, state="readonly", values=config.SEMESTERS)
        self.semester_combo.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=9)
        self.entries["semester"] = self.semester_combo

        tb.Label(left, text="Elective:").grid(row=4, column=0, sticky="w", pady=9)
        self.elective_combo = ttk.Combobox(left, state="readonly")
        self.elective_combo.grid(row=4, column=1, sticky="ew", padx=(10, 0), pady=9)
        self.entries["elective"] = self.elective_combo
        self.branch_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_electives())
        self.semester_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_electives())

        tb.Label(left, text="Email:").grid(row=5, column=0, sticky="w", pady=9)
        email_entry = tb.Entry(left)
        email_entry.grid(row=5, column=1, sticky="ew", padx=(10, 0), pady=9)
        self.entries["email"] = email_entry
        tb.Button(left, text="Suggest", bootstyle="link",
                  command=self.fill_suggested_email).grid(row=5, column=2, padx=(5, 0))

        tb.Label(left, text=f"Pressing Start will open the camera and capture {config.SAMPLES_PER_STUDENT} face\n"
                            "samples automatically. Please face the camera directly.",
                 bootstyle="secondary", justify="left").grid(row=6, column=0, columnspan=3,
                                                              sticky="w", pady=(15, 5))

        btns = tb.Frame(left)
        btns.grid(row=7, column=0, columnspan=3, sticky="w", pady=(15, 0))
        self.start_btn = tb.Button(btns, text="Start Capturing", bootstyle="primary", command=self.start_capturing)
        self.start_btn.grid(row=0, column=0, padx=(0, 8))
        self.cancel_btn = tb.Button(btns, text="Cancel", bootstyle="secondary-outline",
                                    command=self.cancel_capturing, state="disabled")
        self.cancel_btn.grid(row=0, column=1)

        # ---- right: camera ----
        right = tb.Labelframe(body, text="Camera", padding=15)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.video = VideoPanel(right)
        self.video.pack()
        self.progress = tb.Progressbar(right, maximum=config.SAMPLES_PER_STUDENT, bootstyle="success-striped")
        self.progress.pack(fill="x", pady=(12, 4))
        self.status_label = tb.Label(right, text="Ready")
        self.status_label.pack()

    def refresh_branches(self):
        branches = storage.load_branches()
        self.branch_combo["values"] = branches
        self._apply_defaults()

    def _apply_defaults(self):
        """Pre-select the first branch (IT) and the default semester (7) if nothing is chosen yet."""
        branches = list(self.branch_combo["values"])
        if branches and not self.branch_combo.get():
            self.branch_combo.set(branches[0])
        if not self.semester_combo.get():
            self.semester_combo.set(config.DEFAULT_SEMESTER)
        self._refresh_electives()

    def _refresh_electives(self):
        """Elective choices (e.g. CSL / DMMM) for the selected branch + semester."""
        subjects = storage.elective_subjects(self.branch_combo.get(), self.semester_combo.get())
        self._elective_ids = {info["name"]: sid for sid, info in subjects.items()}
        values = ["(none)"] + list(self._elective_ids.keys())
        self.elective_combo["values"] = values
        if self.elective_combo.get() not in values:
            self.elective_combo.set("(none)")

    def fill_suggested_email(self):
        suggestion = suggest_email(self.entries["name"].get(), self.entries["roll"].get(),
                                   self.entries["branch"].get())
        if suggestion:
            self.entries["email"].delete(0, tk.END)
            self.entries["email"].insert(0, suggestion)
        else:
            messagebox.showinfo("Need more info", "Fill Name, Roll No and Branch first.")

    def _set_form_state(self, state):
        for key, e in self.entries.items():
            if key in ("branch", "semester", "elective"):
                e.config(state="readonly" if state == "normal" else "disabled")
            else:
                e.config(state=state)

    def start_capturing(self):
        name = self.entries["name"].get().strip()
        roll_no = self.entries["roll"].get().strip()
        branch = self.entries["branch"].get().strip()
        semester = self.entries["semester"].get().strip()
        email = self.entries["email"].get().strip()
        chosen = self._elective_ids.get(self.elective_combo.get())
        self.electives = [chosen] if chosen else []

        if not name or not roll_no:
            messagebox.showwarning("Missing info", "Please enter at least Name and Roll No.")
            return
        if face_cascade.empty():
            messagebox.showerror("Cascade missing", "haarcascade_frontalface_default.xml was not found in the app.py folder.")
            return

        if not email:
            email = suggest_email(name, roll_no, branch)
            self.entries["email"].insert(0, email)

        self.name, self.roll_no, self.branch, self.semester, self.email = name, roll_no, branch, semester, email
        self.folder = os.path.join(config.DATASET_DIR, f"{roll_no}_{name}")
        self.folder_new = not os.path.exists(self.folder)
        os.makedirs(self.folder, exist_ok=True)

        self.count = 0
        self.last_capture = 0
        self.progress["value"] = 0
        self.capturing = True
        self.active = True
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self._set_form_state("disabled")
        self.status_label.config(text="Connecting...")

        self.camera = CameraStream(config.STREAM_URL)
        self.camera.start()
        self.update_frame()

    def update_frame(self):
        if not self.active:
            return
        cam = self.camera
        frame = cam.get_frame()
        if frame is None:
            self.video.show_message(camera_message(cam))
            self.status_label.config(text="Camera error - retrying..." if cam.status == "error"
                                     else "Connecting...")
        else:
            display = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(60, 60))
            for (x, y, w, h) in faces:
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)

            if self.capturing:
                if len(faces) == 0:
                    self.status_label.config(text="No face detected - please look at the camera")
                elif self.count < config.SAMPLES_PER_STUDENT and time.time() - self.last_capture >= config.CAPTURE_INTERVAL:
                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                    face_img = cv2.resize(gray[y:y + h, x:x + w], (200, 200))
                    if not is_sharp_enough(face_img):
                        self.status_label.config(text="Image blurry - hold still, keep the face in focus")
                    else:
                        self.count += 1
                        self.last_capture = time.time()
                        cv2.imwrite(os.path.join(self.folder, f"{self.count}.jpg"), face_img)
                        self.progress["value"] = self.count
                        self.status_label.config(text=f"Capturing {self.count}/{config.SAMPLES_PER_STUDENT}...")

            self.video.show_frame(display)
            if self.capturing and self.count >= config.SAMPLES_PER_STUDENT:
                self.finish_capturing()
                return
        self.after(30, self.update_frame)

    def _stop_camera(self):
        self.active = False
        self.capturing = False
        if self.camera:
            self.camera.stop()
            self.camera = None

    def finish_capturing(self):
        self._stop_camera()

        labels = storage.load_labels()
        if self.roll_no not in labels:
            labels[self.roll_no] = {"label_id": storage.next_label_id(labels)}
        labels[self.roll_no].update({
            "name": self.name, "branch": self.branch,
            "semester": self.semester, "email": self.email,
            "electives": self.electives,
        })
        storage.save_labels(labels)
        train_model()

        self.status_label.config(text=f"Registered successfully with {self.count} samples!")
        self.video.show_message(f"{self.name} registered successfully!")
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self._set_form_state("normal")
        for key, e in self.entries.items():
            if key in ("branch", "semester", "elective"):
                e.set("")
            else:
                e.delete(0, tk.END)
        self._apply_defaults()

    def cancel_capturing(self):
        was_capturing = self.capturing
        self._stop_camera()
        if was_capturing and self.folder_new and self.folder and os.path.exists(self.folder):
            shutil.rmtree(self.folder, ignore_errors=True)
        self.video.show_message("Camera off")
        self.progress["value"] = 0
        self.status_label.config(text="Cancelled")
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self._set_form_state("normal")

    def on_show(self):
        self.refresh_branches()

    def on_leave(self):
        if self.active:
            self.cancel_capturing()
