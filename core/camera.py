"""
Opens the video stream (Pi feed or a webcam index) on a background thread
so the Tkinter GUI never freezes while connecting or reconnecting.
"""

import time
import threading

import cv2


class CameraStream:
    """Reads frames on a background thread. Call start(), get_frame(), stop()."""

    def __init__(self, source):
        self.source = source
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        self.status = "connecting"   # connecting / connected / error
        self.error = ""

    def start(self):
        self.running = True
        self.status = "connecting"
        threading.Thread(target=self._run, daemon=True).start()

    def _open(self):
        if isinstance(self.source, int):
            return cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
        try:
            return cv2.VideoCapture(
                self.source, cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000],
            )
        except Exception:
            return cv2.VideoCapture(self.source)

    def _release(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        with self.lock:
            self.frame = None

    def _run(self):
        fails = 0
        while self.running:
            if self.cap is None:
                self.status = "connecting"
                self.cap = self._open()
                if not self.cap.isOpened():
                    self.status = "error"
                    self.error = (f"Could not open the stream: {self.source}\n"
                                  "Is the Pi running? Check the URL in a browser, or set the Pi's IP "
                                  "in .env as STREAM_URL.")
                    self._release()
                    time.sleep(2)
                    continue

            ret, frame = self.cap.read()
            if ret and frame is not None:
                fails = 0
                self.status = "connected"
                with self.lock:
                    self.frame = frame
            else:
                fails += 1
                if fails >= 30:
                    self.status = "error"
                    self.error = "Stream stopped sending frames. Check the Pi's camera / WiFi."
                    self._release()
                    fails = 0
                    time.sleep(2)
                else:
                    time.sleep(0.05)
        self._release()

    def get_frame(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False   # the thread releases the capture itself


def camera_message(cam):
    if cam.status == "error":
        return "Could not connect to the camera.\n\n" + cam.error + "\n\nRetrying..."
    return "Connecting to the camera..."
