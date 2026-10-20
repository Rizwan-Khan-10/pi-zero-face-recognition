"""
Small reusable UI pieces shared by every screen: the video canvas,
the screen header bar, the background-task runner, and the table builder.
"""

import re
import threading

import cv2
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tb
from PIL import Image, ImageTk

import config


class VideoPanel(tk.Canvas):
    """Fixed-size pixel canvas for the camera feed - avoids the tk.Label width-in-characters bug."""

    def __init__(self, parent):
        super().__init__(parent, width=config.VIDEO_W, height=config.VIDEO_H, bg="black", highlightthickness=0)
        self._imgtk = None
        self._msg = None
        self.show_message("Camera off")

    def show_frame(self, frame_bgr):
        rgb = cv2.cvtColor(cv2.resize(frame_bgr, (config.VIDEO_W, config.VIDEO_H)), cv2.COLOR_BGR2RGB)
        self._imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._imgtk)
        self._msg = None

    def show_message(self, text):
        if text == self._msg:
            return
        self._msg = text
        self._imgtk = None
        self.delete("all")
        self.create_text(config.VIDEO_W // 2, config.VIDEO_H // 2, text=text, fill="white",
                         font=("Segoe UI", 11), width=config.VIDEO_W - 40, justify="center")


def make_header(parent, title, controller, show_back=True):
    bar = tb.Frame(parent, bootstyle="primary", padding=(20, 12))
    bar.pack(fill="x")
    tb.Label(bar, text=title, font=("Segoe UI", 16, "bold"), bootstyle="inverse-primary").pack(side="left")
    if show_back:
        tb.Button(bar, text="< Home", bootstyle="light",
                  command=lambda: controller.show("HomeScreen")).pack(side="right")
    return bar


def run_in_background(widget, fn, on_done):
    """Runs fn() on a worker thread and calls on_done(result_dict) back on the main thread."""
    result = {}

    def worker():
        try:
            result["value"] = fn()
        except Exception as e:
            result["error"] = str(e)
        result["done"] = True

    threading.Thread(target=worker, daemon=True).start()

    def poll():
        if result.get("done"):
            on_done(result)
        else:
            widget.after(200, poll)

    poll()


def _sort_column(tree, col, numeric, reverse):
    """Click-to-sort a Treeview column. Re-binds itself with the flipped order each click."""
    items = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
    if numeric:
        def key(pair):
            match = re.search(r"-?\d+(?:\.\d+)?", pair[0])
            return float(match.group()) if match else float("-inf")
        items.sort(key=key, reverse=reverse)
    else:
        items.sort(key=lambda pair: pair[0].lower(), reverse=reverse)
    for index, (_, iid) in enumerate(items):
        tree.move(iid, "", index)
    tree.heading(col, command=lambda: _sort_column(tree, col, numeric, not reverse))


def make_table(parent, columns, headings, widths, anchor="center", height=None,
                sortable=True, numeric_columns=()):
    """
    numeric_columns: names of columns (from `columns`) that should sort as
    numbers rather than text, e.g. ("present", "total", "pct").
    """
    frame = tb.Frame(parent)
    kwargs = {"height": height} if height else {}
    tree = ttk.Treeview(frame, columns=columns, show="headings", **kwargs)
    for col, head in zip(columns, headings):
        if sortable:
            tree.heading(col, text=head,
                         command=lambda c=col: _sort_column(tree, c, c in numeric_columns, False))
        else:
            tree.heading(col, text=head)
        tree.column(col, width=widths[col], anchor=anchor, stretch=True)
    yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=yscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    tree.tag_configure("present", foreground="#1a7431")
    tree.tag_configure("absent", foreground="#b3261e")
    tree.tag_configure("low", foreground="#b3261e", background="#fdecea")
    return frame, tree