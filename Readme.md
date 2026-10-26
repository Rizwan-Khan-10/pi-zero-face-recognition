# Face Recognition Attendance System

A face-recognition based attendance system built with a Raspberry Pi Zero W (camera streamer) and a laptop (face detection, recognition, and a Tkinter GUI).

## How it works

The Raspberry Pi Zero W does **no image processing at all**. It just streams the webcam feed over WiFi as MJPEG using Flask. The laptop connects to that stream, runs face detection (OpenCV Haar Cascade) and face recognition (OpenCV LBPH algorithm), and handles registration, attendance marking, and reporting through a GUI.

```
[ Webcam ] --USB(OTG)--> [ Raspberry Pi Zero W ] --WiFi (MJPEG stream)--> [ Laptop: detection + recognition + GUI ]
```

## Repo structure

```
pi_stream_server.py     # Runs on the Pi - streams webcam over WiFi
app.py                  # Runs on the laptop - starts the GUI
config.py               # All settings (stream URL, branches, default semester, minimum attendance %, e-mail ...)
generate_dummy_data.py  # Real + dummy demo data for the presentation (IT, Sem 7)
core/                   # camera, recognition (LBPH), storage (json/csv), reporting maths, e-mail
ui/                     # GUI screens: home, add student, attendance, manage students/branches/subjects, report
requirements.txt        # Laptop-side Python dependencies
.env / .env.example     # E-mail sender + app password (optional)
README.md
```

Also in the folder (generated / local data):
- `haarcascade_frontalface_default.xml` — public OpenCV file (download link in Part 3)
- `dataset/`, `labels.json`, `trainer.yml` — face samples, student list and trained model
- `branches.json`, `subjects.json`, `attendance/` — branches, subjects and the per-day attendance CSVs

---

## What's new in this version

- **Only the IT branch** is set up, with **Semester 7 pre-selected** on every screen (`DEFAULT_BRANCHES` / `DEFAULT_SEMESTER` in `config.py`).
- **Subjects are the University of Mumbai B.E. IT Semester VII (Rev-2019 'C' scheme)** courses: AI and DS - II (ITC701), Internet of Everything (ITC702), Software Testing and QA (ITDO7014, Dept. Optional-3), Information Retrieval System (IRS, Dept. Optional-4), the two Institute Optional-1 courses **Cyber Security and Laws (CSL)** and **Disaster Management and Mitigation Measures (DMMM)**, and the four labs ITL701-ITL704. Software Testing and QA is one common pick for Dept. Optional-3 — rename it in **Manage Subjects** if your batch has a different one.
- **CSL / DMMM are electives**: each student attends only one of them. Pick it in **Add Student** (Elective box) or **Manage Students -> Edit**; the table there has an *Elective* column. Attendance, Finalize and all reports then count only the students of that subject (a student scanned during a lecture of the other elective is boxed orange as "not in this subject" and not marked). A subject becomes an elective by having `"elective": true` in `subjects.json`.
- **Real + dummy students run together**, all IT Sem 7; dummies are never e-mailed and are marked Absent when real attendance is finalized (see "Presentation / demo mode" below).
- **New Attendance Report** with a live *Minimum attendance %* box (see "Attendance report" below).

---

## Attendance report

Open **View Report**. The top bar has Branch / Semester / Subject (default: IT, Sem 7, All Subjects) and, on the right, the **Minimum attendance %** box.

- The box starts at `ATTENDANCE_ELIGIBILITY_THRESHOLD` from `config.py` (**75**). Type any number from 0 to 100 (or use the arrows) and every tab re-colours itself live. **Reset** puts it back to the value in `config.py`. Invalid text is ignored and the last valid value stays. The change lasts until the app is closed; to change the default permanently edit `config.py`.
- A student **below the minimum is shown in red** (and with a `▼` next to that subject's %). Students with no records yet show "No data" and are not counted as short.
- **Semester Summary** (first tab) — the whole semester at a glance, no button to press:
  - *Period* = every day on which attendance was taken. Change **From / To** to look at a smaller range, **Full semester** resets it.
  - Four cards: Students, Meeting the minimum, Below the minimum, Class average.
  - Two charts: students above vs. below the minimum, and the class average per subject (or, for a single subject, how many students fall in each % band).
  - Student table: one **% column per subject** (ITC701 ... IRS, CSL, DMMM ... ITL704; an elective the student does not take shows `-`), then *Attended* (present/total lectures), *Overall %* and *Status* (OK / LOW). Click a heading to sort. Tick **Show only students below minimum** to get a defaulters list.
- **Daily** — Present/Absent for one date. **Weekly** (pick a week by its dates, e.g. "12 Oct - 18 Oct 2026", Monday to Sunday) / **Monthly** (e.g. "October 2026") — chart plus per-student % with the same red highlighting.
- **Export to Excel** on every tab; students below the minimum are filled red in the sheet.

---

## Presentation / demo mode (real + dummy students together)

`generate_dummy_data.py` builds a demo class so the report looks like a real class while the camera still works on the real students:

```
python generate_dummy_data.py                    # full reset (asks before wiping attendance/)
python generate_dummy_data.py --yes              # same, without asking
python generate_dummy_data.py --no-real-history  # real students get no seeded history
```

- **Everything is IT / Sem 7.** All students - real and dummy - belong to IT, semester 7. No other branch or semester data exists.
- **Real students** = everyone who has a face folder in `dataset/<roll>_<Name>/` (currently 231413 Abdullah Ghawte, 231422 Izhar Khan, 231425 Rizwan Khan). The face model is retrained, so the camera recognises them.
- **Electives**: the 3 real students are all in **CSL**. The 40 dummy students are split evenly - 20 in CSL and 20 in DMMM (so CSL has 23 students, DMMM 20). Change anyone in Manage Students.
- **Dummy students** (40, roll numbers 991001 onwards, a separate range so they never clash with real students you add later) have no face data - they only appear in lists and reports. They are flagged `"demo": true` in `labels.json`.
- **Dummy students are never e-mailed.** Their addresses use the reserved `@demo.invalid` domain (`.invalid` can never exist on the internet), **and** the e-mail code skips every demo student on top of that, so even if someone edits a dummy's address nothing is sent. After Finalize the app shows how many demo students were skipped.
- About 90 days of seeded attendance history is written (timetable based; Sundays and a few random holidays skipped). A few dummy students are clearly below 75% and a few sit just around it, so changing the minimum live in the report visibly moves people between green and red. **Today is left empty.**
- The real students also get seeded history (high attendance) so they show up next to the dummies. This is demo data only - use `--no-real-history` to leave them without any.
- **Taking real attendance later:** open **Start Attendance**, pick the subject, let the camera mark the real students, then press **Finalize**. Every student who was not scanned - i.e. **all the dummy students** - is marked **Absent** automatically for that lecture, and only the real students get an e-mail. The same happens when you add a new real student with **Add Student**: the dummies simply stay absent. There is nothing else to run.
- Do **not** re-run the full reset after you have taken real attendance: it wipes `attendance/` and rebuilds the list from `dataset/` (it asks you to type YES first). Students added with **Add Student** are treated as real as long as their face folder exists.

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
5. Set the stream address. Either put `STREAM_URL=http://attendance-pi.local:5000/video_feed` in `.env`, or change the default in `config.py` (use `0` to test with the laptop's own webcam). Update the hostname if you used a different one when flashing the Pi.
6. Make sure `pi_stream_server.py` is running on the Pi first, then run:
   ```
   python app.py
   ```

---

## Usage

- **Add Student** — enter name, roll number, branch (IT) and semester (7 is pre-selected), click "Start Capturing." The camera captures 25 face samples, trains the model, and closes automatically.
- **Start Attendance** — pick branch / semester / subject, click "Start." Recognized faces are boxed with their name and marked "Present" once per day per subject (yellow while confirming, green once marked, orange if the student isn't in that subject). Unrecognized faces show a red box labeled "Unknown."
- **Finalize Lecture (Mark Absentees + Email)** — on the Attendance screen. Marks every student of that subject who wasn't scanned as "Absent" (this includes the dummy students), e-mails the real students their status (never the dummies) and locks the lecture. Do it once, at the end of the lecture.
- **Manage Students / Branches / Subjects** — edit or remove students, add branches, add or remove subjects.
- **View Report** — see "Attendance report" above.

## Data & privacy note

`dataset/`, `labels.json`, `trainer.yml`, and `attendance/` contain student face images and personal attendance records — don't publish them. The dummy data is fake, but the real students' face samples in `dataset/` are not. Also check `.env`: it holds the sender e-mail's app password, so remove it before sharing the project folder.

## Troubleshooting quick reference

| Symptom | Likely cause | Fix |
|---|---|---|
| `ssh: connect ... Connection refused` | Pi still finishing first boot | Wait 1-2 min, retry |
| `VIDIOC_STREAMON: No such device` | USB power drop | Disable autosuspend (see Part 2) |
| Stream loads but is blank/white | Corrupt frame from power drop | Same fix as above |
| `Cannot open device /dev/video0` in OpenCV | Camera not detected, or permissions | Check `lsusb`; add user to `video` group: `sudo usermod -a -G video <username>`, then log out/in |
| `Failed building wheel for dlib` | Not applicable here — this project deliberately avoids `dlib`/`face_recognition` | Use `requirements.txt` as-is (OpenCV LBPH) |
| Pi not visible on network | Wrong WiFi band (5GHz) or wrong SSID/password | Reflash with correct 2.4GHz network details |
| Real student not recognised after running `generate_dummy_data.py` | Model not retrained (OpenCV contrib missing at that moment) | Install `opencv-contrib-python`, run the script again |
| Report shows no students / no data | Wrong branch + semester picked, or `attendance/` is empty | Pick IT / 7, or run `generate_dummy_data.py` (wipes attendance/) |
| Everything is red (or nothing is) in the report | Minimum attendance box is set very high / low | Press **Reset** next to the box (back to 75) |
