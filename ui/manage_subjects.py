"""Manage Subjects screen: add/remove subjects, scoped to a branch + semester."""

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb

import config
from core import storage
from ui.widgets import make_header


class ManageSubjectsScreen(tb.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        make_header(self, "Manage Subjects", controller)

        body = tb.Frame(self, padding=20)
        body.pack(fill="both", expand=True)

        top = tb.Frame(body)
        top.pack(fill="x", pady=(0, 12))
        tb.Label(top, text="Branch:").pack(side="left")
        self.branch_combo = ttk.Combobox(top, state="readonly", width=10)
        self.branch_combo.pack(side="left", padx=(5, 15))
        self.branch_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        tb.Label(top, text="Semester:").pack(side="left")
        self.semester_combo = ttk.Combobox(top, state="readonly", width=6, values=config.SEMESTERS)
        self.semester_combo.pack(side="left", padx=5)
        self.semester_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        content = tb.Frame(body)
        content.pack(fill="both", expand=True)

        left = tb.Labelframe(content, text="Subjects for the selected branch + semester", padding=15)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        list_frame = tb.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_frame, font=("Segoe UI", 11), activestyle="none")
        self.listbox.pack(side="left", fill="both", expand=True)
        yscroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        yscroll.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=yscroll.set)

        tb.Button(left, text="Remove Selected", bootstyle="danger-outline",
                  command=self.remove_selected).pack(fill="x", pady=(10, 0))

        right = tb.Labelframe(content, text="Add Subject", padding=15)
        right.pack(side="left", fill="y", padx=(10, 0))
        tb.Label(right, text="Subject name:").pack(anchor="w")
        self.new_subject_entry = tb.Entry(right, width=22)
        self.new_subject_entry.pack(pady=(5, 10))
        self.new_subject_entry.bind("<Return>", lambda e: self.add_subject())
        tb.Button(right, text="Add", bootstyle="primary", command=self.add_subject).pack(fill="x")
        tb.Label(right, text="Adds to whichever branch +\nsemester is selected on the left.",
                 bootstyle="secondary", justify="left").pack(anchor="w", pady=(20, 0))

        # id -> display text, so Remove can map a listbox selection back to a subject_id
        self._visible_subject_ids = []

    def refresh_branches(self):
        branches = storage.load_branches()
        self.branch_combo["values"] = branches
        if branches and not self.branch_combo.get():
            self.branch_combo.set(branches[0])
        if not self.semester_combo.get():
            self.semester_combo.set(config.DEFAULT_SEMESTER)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        self._visible_subject_ids = []
        branch, semester = self.branch_combo.get(), self.semester_combo.get()
        if not branch or not semester:
            return
        subjects = storage.subjects_for(branch, semester)
        for subject_id, info in sorted(subjects.items(), key=lambda kv: kv[1]["name"]):
            self.listbox.insert(tk.END, info["name"])
            self._visible_subject_ids.append(subject_id)

    def add_subject(self):
        branch, semester = self.branch_combo.get(), self.semester_combo.get()
        if not branch or not semester:
            messagebox.showinfo("Pick branch + semester", "Select a branch and semester first.")
            return
        name = self.new_subject_entry.get().strip()
        if not name:
            return
        existing = storage.subjects_for(branch, semester)
        if any(info["name"].lower() == name.lower() for info in existing.values()):
            messagebox.showinfo("Already exists", f"{name} already exists for {branch} Sem {semester}.")
            return
        storage.add_subject(name, branch, semester)
        self.new_subject_entry.delete(0, tk.END)
        self.refresh_list()

    def remove_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("No selection", "Select a subject first.")
            return
        index = selection[0]
        subject_id = self._visible_subject_ids[index]
        name = self.listbox.get(index)

        if not messagebox.askyesno("Remove subject?",
                                   f"Remove {name}? Past attendance records for it are kept, "
                                   "but it will no longer appear for taking attendance."):
            return

        subjects = storage.load_subjects()
        subjects.pop(subject_id, None)
        storage.save_subjects(subjects)
        self.refresh_list()

    def on_show(self):
        self.refresh_branches()
        self.refresh_list()

    def on_leave(self):
        pass