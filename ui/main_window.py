"""The main Tkinter window: registers every screen and switches between them."""

from tkinter import messagebox
import ttkbootstrap as tb
import cv2

from core.recognition import face_cascade
from ui.home import HomeScreen
from ui.add_student import AddStudentScreen
from ui.manage_students import ManageStudentsScreen
from ui.manage_branches import ManageBranchesScreen
from ui.manage_subjects import ManageSubjectsScreen
from ui.attendance import AttendanceScreen
from ui.report import ReportScreen


class App(tb.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title("Face Recognition Attendance System")
        self.geometry("1100x720")
        self.minsize(1000, 680)

        container = tb.Frame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}
        for ScreenClass in (HomeScreen, AddStudentScreen, AttendanceScreen, ManageStudentsScreen,
                            ManageBranchesScreen, ManageSubjectsScreen, ReportScreen):
            frame = ScreenClass(container, self)
            self.frames[ScreenClass.__name__] = frame
            frame.place(relwidth=1, relheight=1)

        self.current = "HomeScreen"
        self.show("HomeScreen")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if not hasattr(cv2, "face"):
            messagebox.showerror("OpenCV contrib missing",
                                 "cv2.face was not found.\nRun: pip install opencv-contrib-python")
        if face_cascade.empty():
            messagebox.showerror("Cascade missing",
                                 "Place haarcascade_frontalface_default.xml in the app.py folder.")

    def show(self, name):
        current_frame = self.frames[self.current]
        if hasattr(current_frame, "on_leave"):
            current_frame.on_leave()
        new_frame = self.frames[name]
        if hasattr(new_frame, "on_show"):
            new_frame.on_show()
        new_frame.tkraise()
        self.current = name

    def on_close(self):
        for frame in self.frames.values():
            if hasattr(frame, "on_leave"):
                frame.on_leave()
        self.destroy()
