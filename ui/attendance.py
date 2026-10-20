"""Attendance screen: pick branch/semester/subject, live recognition, finalize + lock + email."""

import os
from datetime import datetime

from tkinter import ttk, messagebox
import ttkbootstrap as tb
import cv2

import config
from core import storage
from core.camera import CameraStream, camera_message
from core.recognition import face_cascade
from core.email_service import send_lecture_emails
from ui.widgets import make_header, make_table, VideoPanel, run_in_background


class AttendanceScreen(tb.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.camera = None
        self.running = False
        self.marked_today = set()
        self.recognizer = None
        self.id_to_student = {}
        self.eligible_rolls = []
        self.subject_id = None

        make_header(self, "Attendance", controller)

        # ---- lecture selector ----
        selector = tb.Frame(self, padding=(20, 10, 20, 0))
        selector.pack(fill="x")
        tb.Label(selector, text="Branch:").pack(side="left")
        self.branch_combo = ttk.Combobox(selector, state="readonly", width=10)
        self.branch_combo.pack(side="left", padx=(5, 15))
        self.branch_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_subjects())

        tb.Label(selector, text="Semester:").pack(side="left")
        self.semester_combo = ttk.Combobox(selector, state="readonly", width=6, values=config.SEMESTERS)
        self.semester_combo.pack(side="left", padx=(5, 15))
        self.semester_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_subjects())

        tb.Label(selector, text="Subject:").pack(side="left")
        self.subject_combo = ttk.Combobox(selector, state="readonly", width=24)
        self.subject_combo.pack(side="left", padx=5)
        self.subject_combo.bind("<<ComboboxSelected>>", lambda e: self._on_subject_change())
        self._subject_ids_by_label = {}

        body = tb.Frame(self, padding=20)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ---- left: camera ----
        left = tb.Labelframe(body, text="Live Camera", padding=15)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.video = VideoPanel(left)
        self.video.pack()
        self.status_label = tb.Label(left, text="Pick a branch, semester and subject to begin")
        self.status_label.pack(pady=(10, 0))

        # ---- right: present list ----
        right = tb.Labelframe(body, text="Marked Present This Lecture", padding=15)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        table, self.tree = make_table(
            right, ("name", "roll", "time"), ("Name", "Roll No", "Time"),
            {"name": 180, "roll": 90, "time": 90},
        )
        table.pack(fill="both", expand=True)
        self.count_label = tb.Label(right, text="Present: 0", font=("Segoe UI", 11, "bold"))
        self.count_label.pack(pady=(10, 0))

        # ---- bottom: actions ----
        btns = tb.Frame(body)
        btns.grid(row=1, column=0, columnspan=2, pady=(15, 0))
        self.start_btn = tb.Button(btns, text="▶  Start", bootstyle="success", width=14,
                                   command=self.start_attendance, state="disabled")
        self.start_btn.grid(row=0, column=0, padx=5, ipady=4)
        self.stop_btn = tb.Button(btns, text="■  Stop", bootstyle="danger", width=14,
                                  command=self.stop_attendance, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=5, ipady=4)
        self.finalize_btn = tb.Button(btns, text="✓  Finalize Lecture (Mark Absentees + Email)",
                                      bootstyle="warning", command=self.finalize_lecture, state="disabled")
        self.finalize_btn.grid(row=0, column=2, padx=5, ipady=4)

    # ---------------- lecture selection ----------------

    def _refresh_branches(self):
        branches = storage.load_branches()
        current = self.branch_combo.get()
        self.branch_combo["values"] = branches
        if branches and not current:
            self.branch_combo.set(branches[0])
        if not self.semester_combo.get():
            self.semester_combo.set(config.DEFAULT_SEMESTER)
        self._refresh_subjects()

    def _refresh_subjects(self):
        branch, semester = self.branch_combo.get(), self.semester_combo.get()
        subjects = storage.subjects_for(branch, semester) if branch and semester else {}
        self._subject_ids_by_label = {info["name"]: sid for sid, info in subjects.items()}
        names = sorted(self._subject_ids_by_label.keys())
        self.subject_combo["values"] = names
        if names:
            if self.subject_combo.get() not in names:
                self.subject_combo.set(names[0])
        else:
            self.subject_combo.set("")
        self._on_subject_change()

    def _on_subject_change(self):
        name = self.subject_combo.get()
        self.subject_id = self._subject_ids_by_label.get(name)
        branch, semester = self.branch_combo.get(), self.semester_combo.get()
        self.eligible_rolls = (storage.students_for_subject(branch, semester, self.subject_id)
                               if branch and semester and self.subject_id else [])
        self.reload_list()

        if not self.subject_id:
            self.start_btn.config(state="disabled")
            self.finalize_btn.config(state="disabled")
            self.status_label.config(text="No subjects for this branch + semester yet - add one in Manage Subjects")
            return

        if not self.eligible_rolls:
            self.start_btn.config(state="disabled")
            self.finalize_btn.config(state="disabled")
            self.status_label.config(text="No students registered for this subject yet (electives: set the student's elective in Manage Students)")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        if storage.is_finalized(today, self.subject_id):
            self.start_btn.config(state="disabled")
            self.finalize_btn.config(state="disabled")
            self.status_label.config(text="This lecture is already finalized for today")
        else:
            self.start_btn.config(state="normal")
            self.finalize_btn.config(state="normal")
            self.status_label.config(text="Ready - press Start")

    # ---------------- attendance list ----------------

    def reload_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not self.subject_id:
            self.count_label.config(text="Present: 0")
            return
        today = datetime.now().strftime("%Y-%m-%d")
        present = [r for r in storage.read_subject_rows(today, self.subject_id) if r[3] == "Present"]
        for roll_no, name, time_str, _ in reversed(present):
            self.tree.insert("", "end", values=(name, roll_no, time_str))
        self.count_label.config(text=f"Present: {len(present)}")

    # ---------------- start / live recognition ----------------

    def start_attendance(self):
        if not self.subject_id:
            messagebox.showwarning("No subject selected", "Pick a branch, semester and subject first.")
            return
        today = datetime.now().strftime("%Y-%m-%d")
        if storage.is_finalized(today, self.subject_id):
            messagebox.showinfo("Already finalized", "This lecture has already been finalized for today.")
            return
        if not os.path.exists(config.MODEL_FILE) or not os.path.exists(config.LABELS_FILE):
            messagebox.showerror("No model", "No registered students found. Add a student first.")
            return
        if face_cascade.empty():
            messagebox.showerror("Cascade missing", "haarcascade_frontalface_default.xml was not found in the app.py folder.")
            return

        labels = storage.load_labels()
        self.id_to_student = {v["label_id"]: (roll_no, v.get("name", "")) for roll_no, v in labels.items()}
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.recognizer.read(config.MODEL_FILE)
        self.marked_today = storage.load_marked_today(self.subject_id)
        self.reload_list()

        self.camera = CameraStream(config.STREAM_URL)
        self.camera.start()
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.branch_combo.config(state="disabled")
        self.semester_combo.config(state="disabled")
        self.subject_combo.config(state="disabled")
        self.status_label.config(text="Connecting...")
        self.update_frame()

    def update_frame(self):
        if not self.running:
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
            today = datetime.now().strftime("%Y-%m-%d")

            for (x, y, w, h) in faces:
                face_img = cv2.resize(gray[y:y + h, x:x + w], (200, 200))
                label_id, confidence = self.recognizer.predict(face_img)
                name, color = "Unknown", (0, 0, 255)

                if confidence < config.CONFIDENCE_THRESHOLD and label_id in self.id_to_student:
                    roll_no, name = self.id_to_student[label_id]
                    if roll_no not in self.eligible_rolls:
                        name = f"{name} (not in this subject)"
                        color = (0, 165, 255)
                    else:
                        color = (0, 255, 0)
                        if roll_no not in self.marked_today:
                            storage.mark_present(today, self.subject_id, roll_no, self.id_to_student[label_id][1])
                            self.marked_today.add(roll_no)
                            self.tree.insert("", 0, values=(self.id_to_student[label_id][1], roll_no,
                                                            datetime.now().strftime("%H:%M:%S")))
                            self.count_label.config(text=f"Present: {len(self.tree.get_children())}")

                cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
                cv2.putText(display, name, (x, max(y - 10, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            self.video.show_frame(display)
            self.status_label.config(text="Live - scanning...")
        self.after(30, self.update_frame)

    def stop_attendance(self):
        self.running = False
        if self.camera:
            self.camera.stop()
            self.camera = None
        self.video.show_message("Camera off")
        self.status_label.config(text="Stopped")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.branch_combo.config(state="readonly")
        self.semester_combo.config(state="readonly")
        self.subject_combo.config(state="readonly")

    # ---------------- finalize ----------------

    def finalize_lecture(self):
        if not self.subject_id:
            messagebox.showwarning("No subject selected", "Pick a branch, semester and subject first.")
            return
        today = datetime.now().strftime("%Y-%m-%d")
        if storage.is_finalized(today, self.subject_id):
            messagebox.showinfo("Already finalized", "This lecture has already been finalized for today.")
            return

        subject_name = self.subject_combo.get()
        if not messagebox.askyesno(
                "Finalize lecture?",
                f"This will mark every student of this branch + semester who wasn't scanned for "
                f"'{subject_name}' today as Absent, email each student their status, and lock this "
                "lecture.\n\nAfter this, you will NOT be able to mark attendance again for this "
                "subject today. Continue?"):
            return

        self.stop_attendance()
        absent_count = storage.finalize_absentees(today, self.subject_id, self.eligible_rolls)
        storage.mark_finalized(today, self.subject_id)
        self.start_btn.config(state="disabled")
        self.finalize_btn.config(state="disabled")
        self.reload_list()

        if not config.EMAIL_ENABLED:
            messagebox.showinfo(
                "Done",
                f"{absent_count} student(s) marked absent. This lecture is now locked.\n"
                "Email sending is OFF - set EMAIL_ENABLED=true in .env to send emails."
            )
            return

        self.status_label.config(text="Sending emails... please wait")
        run_in_background(self, lambda: send_lecture_emails(today, self.subject_id),
                          lambda res: self._emails_done(absent_count, res))

    def _emails_done(self, absent_count, res):
        self.status_label.config(text="This lecture is finalized.")
        if "error" in res:
            messagebox.showerror("Email error", res["error"])
            return
        sent, failures = res["value"]
        msg = f"{absent_count} student(s) marked absent. This lecture is now locked.\nEmails sent: {sent}, failed: {len(failures)}."
        if failures:
            msg += "\n\nFailed:\n" + "\n".join(failures[:8])
            if len(failures) > 8:
                msg += f"\n...and {len(failures) - 8} more"
        messagebox.showinfo("Done", msg)

    # ---------------- lifecycle ----------------

    def on_show(self):
        self._refresh_branches()

    def on_leave(self):
        self.stop_attendance()