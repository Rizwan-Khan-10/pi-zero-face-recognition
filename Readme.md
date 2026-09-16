# Face Recognition Attendance System

A face-recognition based attendance system built with a Raspberry Pi Zero W (camera streamer) and a laptop (face detection, recognition, and a Tkinter GUI).

## How it works

The Raspberry Pi Zero W does **no image processing at all**. It just streams the webcam feed over WiFi as MJPEG using Flask. The laptop connects to that stream, runs face detection (OpenCV Haar Cascade) and face recognition (OpenCV LBPH algorithm), and handles registration, attendance marking, and reporting through a GUI.

```
[ Webcam ] --USB(OTG)--> [ Raspberry Pi Zero W ] --WiFi (MJPEG stream)--> [ Laptop: detection + recognition + GUI ]
```

## Repo structure

```
pi_stream_server.py   # Runs on the Pi - streams webcam over WiFi
app.py                # Runs on the laptop - GUI (register, attendance, report)
requirements.txt      # Laptop-side Python dependencies
.gitignore
README.md
```

Not included in the repo (see setup steps below for how each is created):
- `haarcascade_frontalface_default.xml` — public OpenCV file, download separately
- `dataset/`, `labels.json`, `trainer.yml` — generated when you register students
- `attendance/` — generated when you take attendance

---

## Part 1 — Flash the Raspberry Pi (headless setup)

**Hardware needed:** Raspberry Pi Zero W, a microSD card (8GB+), a microSD card reader, a USB webcam, a micro-USB OTG adapter, a good 5V power source, a WiFi network (a phone hotspot works fine).

1. Install **Raspberry Pi Imager** on your computer.
2. Insert the microSD card via a card reader.
3. Open Imager → **Choose Device** → Raspberry Pi Zero.
4. **Choose OS** → "Raspberry Pi OS (other)" → **Raspberry Pi OS Lite (32-bit)**.
   (Do NOT pick the plain "Raspberry Pi OS (32-bit)" — that's the Desktop version and is too heavy for a Zero W's 512MB RAM.)
5. **Choose Storage** → select your SD card.
6. Click the **gear/settings icon** before writing, and set:
   - **Hostname**: e.g. `attendance-pi`
   - **Username/Password**: your choice, write it down
   - **Wi-Fi**: your SSID + password + country code. **Important: the Pi Zero W only supports 2.4GHz WiFi.** If using a phone hotspot, make sure it's not forced to 5GHz.
   - **Enable SSH** (under Remote Access / Services tab), with password authentication
   - Locale/timezone as needed
7. Save, then click **Write**, confirm erase, and wait (~10–20 min).
8. Insert the SD card into the Pi, connect power, wait ~1–2 min for first boot.

### Connecting

```
ping <hostname>.local          # e.g. ping attendance-pi.local
ssh <username>@<hostname>.local
```

If `ssh` gives "Connection refused," wait another minute or two — first boot takes time to bring services up.

### Using someone else's phone hotspot later

The Pi only cares about SSID + password, not whose phone it is. If your hotspot isn't available, anyone can create a hotspot with the **exact same SSID and password** (2.4GHz), and the Pi/laptop will connect exactly as before.

---

## Part 2 — Pi-side setup (webcam + streaming server)

1. Update the system:
   ```
   sudo apt update && sudo apt upgrade -y
   ```
2. Install dependencies:
   ```
   sudo apt install python3-opencv python3-flask python3-pip -y
   ```
3. **Connect the webcam.** The Pi Zero W has two micro-USB ports — one labeled `PWR IN` (power only) and one plain `USB` (data). Plug your OTG adapter + webcam into the `USB` port. Keep power going into `PWR IN`.
4. Check the webcam is detected:
   ```
   lsusb
   ls /dev/video0
   ```

### Known issue: webcam disconnects / "VIDIOC_STREAMON: No such device" / blank stream

The Pi Zero W's USB port can't always supply enough current when a webcam starts streaming, causing it to disconnect mid-capture. Fix by disabling USB autosuspend:

**Quick test (temporary, resets on reboot):**
```
echo -1 | sudo tee /sys/module/usbcore/parameters/autosuspend
```

**Permanent fix:**
```
sudo nano /boot/firmware/cmdline.txt
```
Add this to the **end of the single existing line** (space-separated, don't add a new line):
```
usbcore.autosuspend=-1
```
Save (`Ctrl+X`, `Y`, `Enter`), then:
```
sudo reboot
```

If it still disconnects, use a **powered USB hub** (one with its own separate power adapter) between the Pi and the webcam — a USB-C laptop dock/hub is NOT a substitute, it needs to be a hub with its own DC power input.

5. Copy `pi_stream_server.py` to the Pi (run this from your laptop, not the Pi):
   ```
   scp pi_stream_server.py <username>@<hostname>.local:~/
   ```
6. Run it on the Pi:
   ```
   python3 pi_stream_server.py
   ```
   Leave this running. You should see `Running on http://0.0.0.0:5000`.
7. Test from any browser: `http://<hostname>.local:5000/video_feed` should show a live feed.

(Optional) To auto-start this on boot, set it up as a `systemd` service so you don't need to SSH in every time.

---

## Part 3 — Laptop-side setup

1. Clone this repo and open a terminal in it.
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # macOS/Linux
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   (Deliberately uses OpenCV's built-in LBPH recognizer instead of `dlib`/`face_recognition` — the latter needs Visual Studio C++ Build Tools to compile on Windows, which is a common blocker. `opencv-contrib-python` installs from a prebuilt wheel with no compilation needed.)
4. Download the face detector file and place it in the project's root folder (same folder as `app.py`):
   [haarcascade_frontalface_default.xml](https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml)
   (Save As, keep the exact filename.)
5. Open `app.py` and `pi_stream_server.py`'s companion — check the `STREAM_URL` constant near the top of `app.py`:
   ```python
   STREAM_URL = "http://attendance-pi.local:5000/video_feed"
   ```
   Update the hostname if you used a different one when flashing the Pi.
6. Make sure `pi_stream_server.py` is running on the Pi first, then run:
   ```
   python app.py
   ```

---

## Usage

- **Add Student** — enter name and roll number, click "Start Capturing." The camera feed opens automatically, captures 25 face samples, trains the model, and closes automatically. No manual photo-taking needed.
- **Start Attendance** — click "Start." Recognized faces are boxed in green with their name and marked "Present" once per day automatically. Unrecognized faces show a red box labeled "Unknown."
- **Finalize Day (Mark Absentees)** — on the Attendance screen. Marks every registered student who wasn't scanned that day as "Absent" in the day's record. Confirm before using — this is meant to be done once, at the end of the attendance window.
- **View Report** — pick a date from the dropdown to see a table of everyone's status for that day.

## Data & privacy note

`dataset/`, `labels.json`, `trainer.yml`, and `attendance/` are gitignored on purpose — they contain student face images and personal attendance records. Each deployment generates its own fresh copies; nothing here should be committed or shared publicly.

## Troubleshooting quick reference

| Symptom | Likely cause | Fix |
|---|---|---|
| `ssh: connect ... Connection refused` | Pi still finishing first boot | Wait 1-2 min, retry |
| `VIDIOC_STREAMON: No such device` | USB power drop | Disable autosuspend (see Part 2) |
| Stream loads but is blank/white | Corrupt frame from power drop | Same fix as above |
| `Cannot open device /dev/video0` in OpenCV | Camera not detected, or permissions | Check `lsusb`; add user to `video` group: `sudo usermod -a -G video <username>`, then log out/in |
| `Failed building wheel for dlib` | Not applicable here — this project deliberately avoids `dlib`/`face_recognition` | Use `requirements.txt` as-is (OpenCV LBPH) |
| Pi not visible on network | Wrong WiFi band (5GHz) or wrong SSID/password | Reflash with correct 2.4GHz network details |