"""Home / dashboard screen: stats, quick actions, today's activity table."""

from datetime import datetime

import tkinter as tk
import ttkbootstrap as tb

from core import storage
from ui.widgets import make_header, make_table


class HomeScreen(tb.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        bar = make_header(self, "Face Recognition Attendance System", controller, show_back=False)
        self.date_label = tb.Label(bar, bootstyle="inverse-primary", font=("Segoe UI", 11))
        self.date_label.pack(side="right")

        body = tb.Frame(self, padding=25)
        body.pack(fill="both", expand=True)

        stats = tb.Frame(body)
        stats.pack(fill="x")
        for i in range(3):
            stats.columnconfigure(i, weight=1, uniform="stat")
        self.total_var = tk.StringVar(value="0")
        self.classes_var = tk.StringVar(value="0")
        self.present_var = tk.StringVar(value="0")
        self._stat_card(stats, "Total Students", self.total_var, "info", 0)
        self._stat_card(stats, "Classes Held Today", self.classes_var, "secondary", 1)
        self._stat_card(stats, "Present Markings Today", self.present_var, "success", 2)

        actions = tb.Frame(body)
        actions.pack(fill="x", pady=22)
        items = [
            ("➕  Add Student", "primary", "AddStudentScreen"),
            ("▶  Start Attendance", "success", "AttendanceScreen"),
            ("👥  Manage Students", "secondary", "ManageStudentsScreen"),
            ("🏷  Manage Branches", "dark", "ManageBranchesScreen"),
            ("📘  Manage Subjects", "dark", "ManageSubjectsScreen"),
            ("📊  View Report", "info", "ReportScreen"),
        ]
        for i, (text, style, target) in enumerate(items):
            actions.columnconfigure(i, weight=1, uniform="act")
            tb.Button(actions, text=text, bootstyle=style,
                      command=lambda t=target: controller.show(t)).grid(
                row=0, column=i, sticky="ew", padx=6, ipady=14)

        recent = tb.Labelframe(body, text="Today's Activity", padding=10)
        recent.pack(fill="both", expand=True)
        table, self.tree = make_table(
            recent, ("subject", "roll", "name", "time", "status"),
            ("Subject", "Roll No", "Name", "Time", "Status"),
            {"subject": 170, "roll": 90, "name": 200, "time": 100, "status": 100},
        )
        table.pack(fill="both", expand=True)

    def _stat_card(self, parent, label, var, style, col):
        card = tb.Frame(parent, bootstyle=style, padding=18)
        card.grid(row=0, column=col, padx=6, sticky="ew")
        tb.Label(card, textvariable=var, font=("Segoe UI", 26, "bold"), bootstyle=f"inverse-{style}").pack()
        tb.Label(card, text=label, font=("Segoe UI", 11), bootstyle=f"inverse-{style}").pack()

    def on_show(self):
        self.date_label.config(text=datetime.now().strftime("%A, %d %B %Y"))
        today = datetime.now().strftime("%Y-%m-%d")
        subject_ids = storage.list_subjects_recorded_on(today)
        subjects_db = storage.load_subjects()

        self.total_var.set(str(len(storage.load_labels())))
        self.classes_var.set(str(len(subject_ids)))

        for item in self.tree.get_children():
            self.tree.delete(item)

        all_rows = []
        present_count = 0
        for subject_id in subject_ids:
            subject_name = subjects_db.get(subject_id, {}).get("name", subject_id)
            for row in storage.read_subject_rows(today, subject_id):
                all_rows.append((subject_name, row))
                if row[3] == "Present":
                    present_count += 1
        self.present_var.set(str(present_count))

        for subject_name, row in reversed(all_rows):
            roll_no, name, time_str, status = row[:4]
            self.tree.insert("", "end", values=(subject_name, roll_no, name, time_str, status),
                             tags=("present" if status == "Present" else "absent",))

    def on_leave(self):
        pass
