"""Manage Students screen: table of registered students, edit / delete."""

import os
import shutil

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb

import config
from core import storage
from core.recognition import train_model
from ui.widgets import make_header, make_table


class ManageStudentsScreen(tb.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        make_header(self, "Manage Students", controller)

        body = tb.Frame(self, padding=20)
        body.pack(fill="both", expand=True)

        filters = tb.Frame(body)
        filters.pack(fill="x", pady=(0, 10))
        tb.Label(filters, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_table())
        tb.Entry(filters, textvariable=self.search_var, width=25).pack(side="left", padx=(5, 15))

        tb.Label(filters, text="Branch:").pack(side="left")
        self.branch_filter = ttk.Combobox(filters, state="readonly", width=10)
        self.branch_filter.pack(side="left", padx=(5, 15))
        self.branch_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        tb.Label(filters, text="Semester:").pack(side="left")
        self.semester_filter = ttk.Combobox(filters, state="readonly", width=6,
                                            values=["All"] + config.SEMESTERS)
        self.semester_filter.set(config.DEFAULT_SEMESTER)
        self.semester_filter.pack(side="left", padx=5)
        self.semester_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        self.count_label = tb.Label(filters, text="", bootstyle="secondary")
        self.count_label.pack(side="right")

        table, self.tree = make_table(
            body, ("roll", "name", "branch", "semester", "elective", "email"),
            ("Roll No", "Name", "Branch", "Sem", "Elective", "Email"),
            {"roll": 100, "name": 200, "branch": 80, "semester": 60, "elective": 90, "email": 280},
            anchor="w", numeric_columns=("roll", "semester"),
        )
        table.pack(fill="both", expand=True)

        btns = tb.Frame(body)
        btns.pack(pady=(15, 0))
        tb.Button(btns, text="Edit Selected", bootstyle="primary", command=self.edit_selected).grid(row=0, column=0, padx=5)
        tb.Button(btns, text="Delete Selected", bootstyle="danger", command=self.delete_selected).grid(row=0, column=1, padx=5)
        tb.Button(btns, text="Refresh", bootstyle="secondary", command=self.refresh_table).grid(row=0, column=2, padx=5)

    def refresh_filters(self):
        branches = ["All"] + storage.load_branches()
        current = self.branch_filter.get()
        self.branch_filter["values"] = branches
        self.branch_filter.set(current if current in branches else "All")

    def refresh_table(self):
        self.refresh_filters()
        for row in self.tree.get_children():
            self.tree.delete(row)

        query = self.search_var.get().strip().lower()
        branch_filter = self.branch_filter.get()
        semester_filter = self.semester_filter.get()

        all_students = storage.load_labels()
        shown = 0
        for roll_no, info in all_students.items():
            name = info.get("name", "")
            branch = info.get("branch", "")
            semester = info.get("semester", "")

            if query and query not in name.lower() and query not in roll_no.lower():
                continue
            if branch_filter not in ("", "All") and branch != branch_filter:
                continue
            if semester_filter not in ("", "All") and semester != semester_filter:
                continue

            self.tree.insert("", "end", iid=roll_no, values=(
                roll_no, name, branch, semester, _elective_text(info), info.get("email", "")
            ))
            shown += 1

        total = len(all_students)
        self.count_label.config(text=f"Showing {shown} of {total} students" if shown != total
                                else f"{total} students")

    def edit_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "Select a student first.")
            return
        roll_no = selected[0]
        info = storage.load_labels().get(roll_no, {})
        EditStudentDialog(self, roll_no, info, self.refresh_table)

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "Select a student first.")
            return
        roll_no = selected[0]
        labels = storage.load_labels()
        name = labels.get(roll_no, {}).get("name", "")

        if not messagebox.askyesno(
                "Delete student?",
                f"This will permanently delete {name} ({roll_no}) and their face data. Continue?"):
            return

        folder = os.path.join(config.DATASET_DIR, f"{roll_no}_{name}")
        if os.path.exists(folder):
            shutil.rmtree(folder)
        if roll_no in labels:
            del labels[roll_no]
            storage.save_labels(labels)

        train_model()
        self.refresh_table()
        messagebox.showinfo("Deleted", f"{name} ({roll_no}) has been removed.")

    def on_show(self):
        self.refresh_table()

    def on_leave(self):
        pass


def _elective_text(info):
    """Short text for the Elective column, e.g. 'CSL' (uses the subject's code/short name)."""
    subjects = storage.load_subjects()
    parts = [subjects[sid].get("code") or subjects[sid]["name"]
             for sid in info.get("electives", []) if sid in subjects]
    return ", ".join(parts) if parts else "-"


class EditStudentDialog(tb.Toplevel):
    def __init__(self, parent, roll_no, info, on_save_callback):
        super().__init__(parent)
        self.title(f"Edit {roll_no}")
        self.roll_no = roll_no
        self.on_save_callback = on_save_callback
        self.old_name = info.get("name", "")

        self.entries = {}
        text_fields = [("Name", "name"), ("Email", "email")]
        for i, (label, key) in enumerate(text_fields):
            tb.Label(self, text=f"{label}:").grid(row=i, column=0, sticky="e", padx=10, pady=8)
            entry = tb.Entry(self, width=32)
            entry.insert(0, info.get(key, ""))
            entry.grid(row=i, column=1, padx=10, pady=8)
            self.entries[key] = entry

        tb.Label(self, text="Branch:").grid(row=2, column=0, sticky="e", padx=10, pady=8)
        branch_combo = ttk.Combobox(self, width=29, state="readonly", values=storage.load_branches())
        branch_combo.set(info.get("branch", ""))
        branch_combo.grid(row=2, column=1, padx=10, pady=8)
        self.entries["branch"] = branch_combo

        tb.Label(self, text="Semester:").grid(row=3, column=0, sticky="e", padx=10, pady=8)
        semester_combo = ttk.Combobox(self, width=29, state="readonly", values=config.SEMESTERS)
        semester_combo.set(info.get("semester", ""))
        semester_combo.grid(row=3, column=1, padx=10, pady=8)
        self.entries["semester"] = semester_combo

        tb.Label(self, text="Elective:").grid(row=4, column=0, sticky="e", padx=10, pady=8)
        self._elective_ids = {}
        elective_combo = ttk.Combobox(self, width=29, state="readonly")
        elective_combo.grid(row=4, column=1, padx=10, pady=8)
        self.entries["elective"] = elective_combo
        branch_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_electives(info))
        semester_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_electives(info))
        self._refresh_electives(info)

        fields = text_fields + [("Branch", "branch"), ("Semester", "semester"), ("Elective", "elective")]

        tb.Button(self, text="Save", bootstyle="success", command=self.save).grid(row=len(fields), column=0, pady=15)
        tb.Button(self, text="Cancel", bootstyle="secondary", command=self.destroy).grid(row=len(fields), column=1, pady=15)

    def _refresh_electives(self, info):
        """Elective choices for the branch + semester currently picked in this dialog."""
        subjects = storage.elective_subjects(self.entries["branch"].get().strip(),
                                             self.entries["semester"].get().strip())
        self._elective_ids = {s["name"]: sid for sid, s in subjects.items()}
        combo = self.entries["elective"]
        combo["values"] = ["(none)"] + list(self._elective_ids.keys())
        current = [s["name"] for sid, s in subjects.items() if sid in info.get("electives", [])]
        if combo.get() not in combo["values"]:
            combo.set(current[0] if current else "(none)")

    def save(self):
        labels = storage.load_labels()
        if self.roll_no not in labels:
            messagebox.showerror("Error", "Student not found.")
            self.destroy()
            return

        new_name = self.entries["name"].get().strip()
        old_folder = os.path.join(config.DATASET_DIR, f"{self.roll_no}_{self.old_name}")
        new_folder = os.path.join(config.DATASET_DIR, f"{self.roll_no}_{new_name}")
        if new_name != self.old_name and os.path.exists(old_folder):
            os.rename(old_folder, new_folder)

        labels[self.roll_no]["name"] = new_name
        labels[self.roll_no]["branch"] = self.entries["branch"].get().strip()
        labels[self.roll_no]["semester"] = self.entries["semester"].get().strip()
        labels[self.roll_no]["email"] = self.entries["email"].get().strip()
        chosen = self._elective_ids.get(self.entries["elective"].get())
        labels[self.roll_no]["electives"] = [chosen] if chosen else []
        storage.save_labels(labels)

        self.on_save_callback()
        self.destroy()