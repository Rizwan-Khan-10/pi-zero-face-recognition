"""Manage Branches screen: add/remove branches. Semesters are always fixed 1-8."""

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb

from core import storage
from ui.widgets import make_header


class ManageBranchesScreen(tb.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        make_header(self, "Manage Branches", controller)

        body = tb.Frame(self, padding=20)
        body.pack(fill="both", expand=True)

        tb.Label(body, text="Every branch always has 8 semesters (1 to 8). Add or remove branches below.",
                 bootstyle="secondary").pack(anchor="w", pady=(0, 12))

        content = tb.Frame(body)
        content.pack(fill="both", expand=True)

        left = tb.Labelframe(content, text="Branches", padding=15)
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

        right = tb.Labelframe(content, text="Add Branch", padding=15)
        right.pack(side="left", fill="y", padx=(10, 0))
        tb.Label(right, text="Branch name:").pack(anchor="w")
        self.new_branch_entry = tb.Entry(right, width=20)
        self.new_branch_entry.pack(pady=(5, 10))
        self.new_branch_entry.bind("<Return>", lambda e: self.add_branch())
        tb.Button(right, text="Add", bootstyle="primary", command=self.add_branch).pack(fill="x")
        tb.Label(right, text="Semesters for every branch:\n1, 2, 3, 4, 5, 6, 7, 8",
                 bootstyle="secondary", justify="left").pack(anchor="w", pady=(20, 0))

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for branch in storage.load_branches():
            self.listbox.insert(tk.END, branch)

    def add_branch(self):
        name = self.new_branch_entry.get().strip().upper()
        if not name:
            return
        branches = storage.load_branches()
        if name in branches:
            messagebox.showinfo("Already exists", f"{name} is already in the list.")
            return
        branches.append(name)
        storage.save_branches(branches)
        self.new_branch_entry.delete(0, tk.END)
        self.refresh_list()

    def remove_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("No selection", "Select a branch first.")
            return
        name = self.listbox.get(selection[0])
        in_use = [info.get("name", roll) for roll, info in storage.load_labels().items() if info.get("branch") == name]
        if in_use:
            messagebox.showwarning(
                "Branch in use",
                f"Cannot remove {name} - it is assigned to: {', '.join(in_use[:5])}"
                + (f" and {len(in_use) - 5} more" if len(in_use) > 5 else "")
                + ".\nChange their branch first in Manage Students."
            )
            return
        if not messagebox.askyesno("Remove branch?", f"Remove {name} from the branch list?"):
            return
        branches = [b for b in storage.load_branches() if b != name]
        storage.save_branches(branches)
        self.refresh_list()

    def on_show(self):
        self.refresh_list()

    def on_leave(self):
        pass
