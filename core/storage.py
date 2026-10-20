"""
All reading/writing of labels.json, branches.json, subjects.json, and
attendance records. No UI code, no camera code.

Attendance layout (subject-aware, since a day can have several lectures):
    attendance/<date>/<subject_id>.csv      - one file per subject per day
    attendance/<date>/finalized.json        - list of subject_ids finalized that day
"""

import os
import re
import csv
import json
from datetime import datetime

import config


# ---------------- students (labels.json) ----------------

def load_labels():
    if os.path.exists(config.LABELS_FILE):
        with open(config.LABELS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_labels(labels):
    with open(config.LABELS_FILE, "w") as f:
        json.dump(labels, f, indent=2)


def next_label_id(labels):
    return max([v["label_id"] for v in labels.values()], default=-1) + 1


def students_for(branch, semester):
    """Roll numbers of registered students in this branch + semester."""
    return [roll for roll, info in load_labels().items()
            if info.get("branch") == branch and info.get("semester") == semester]


# ---------------- electives (students who take only some subjects) ----------------
# A subject flagged  "elective": true  in subjects.json (e.g. CSL / DMMM) is attended only by the
# students whose labels.json entry lists that subject_id under "electives".

def students_for_subject(branch, semester, subject_id):
    """Roll numbers who actually attend this subject (everyone, unless it is an elective)."""
    rolls = students_for(branch, semester)
    if not load_subjects().get(subject_id, {}).get("elective"):
        return rolls
    labels = load_labels()
    return [r for r in rolls if subject_id in labels.get(r, {}).get("electives", [])]


def students_for_subjects(branch, semester, subject_ids):
    """Union of students_for_subject over several subjects, in roll order, no duplicates."""
    wanted = set()
    for sid in subject_ids:
        wanted.update(students_for_subject(branch, semester, sid))
    return [r for r in students_for(branch, semester) if r in wanted]


def elective_subjects(branch, semester):
    """{subject_id: info} of the elective subjects of this branch + semester."""
    return {sid: s for sid, s in subjects_for(branch, semester).items() if s.get("elective")}


# ---------------- branches (branches.json) ----------------

def load_branches():
    if os.path.exists(config.BRANCHES_FILE):
        with open(config.BRANCHES_FILE, "r") as f:
            return json.load(f)
    save_branches(config.DEFAULT_BRANCHES)
    return list(config.DEFAULT_BRANCHES)


def save_branches(branches):
    with open(config.BRANCHES_FILE, "w") as f:
        json.dump(branches, f, indent=2)


# ---------------- subjects (subjects.json) ----------------

def load_subjects():
    """{subject_id: {"name": ..., "branch": ..., "semester": ...}}"""
    if os.path.exists(config.SUBJECTS_FILE):
        with open(config.SUBJECTS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_subjects(subjects):
    with open(config.SUBJECTS_FILE, "w") as f:
        json.dump(subjects, f, indent=2)


def make_subject_id(branch, semester, name):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name.strip()).strip("-").upper()
    return f"{branch}-{semester}-{slug}"


def add_subject(name, branch, semester):
    subjects = load_subjects()
    subject_id = make_subject_id(branch, semester, name)
    subjects[subject_id] = {"name": name.strip(), "branch": branch, "semester": semester}
    save_subjects(subjects)
    return subject_id


def subjects_for(branch, semester):
    """{subject_id: info} for subjects belonging to this branch + semester."""
    return {sid: s for sid, s in load_subjects().items()
            if s.get("branch") == branch and s.get("semester") == semester}


def subject_label(subject_id):
    s = load_subjects().get(subject_id)
    if not s:
        return subject_id
    return f"{s['name']} ({s['branch']} Sem {s['semester']})"


# ---------------- attendance: per date + subject ----------------

def _day_dir(date):
    return os.path.join(config.ATTENDANCE_DIR, date)


def _subject_file(date, subject_id):
    return os.path.join(_day_dir(date), f"{subject_id}.csv")


def _finalized_file(date):
    return os.path.join(_day_dir(date), "finalized.json")


def read_csv_rows(path):
    rows = []
    if os.path.exists(path):
        with open(path, "r") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 4:
                    rows.append(row)
    return rows


def read_subject_rows(date, subject_id):
    return read_csv_rows(_subject_file(date, subject_id))


def load_marked_today(subject_id):
    date = datetime.now().strftime("%Y-%m-%d")
    return {row[0] for row in read_subject_rows(date, subject_id)}


def _append_subject_row(date, subject_id, row):
    os.makedirs(_day_dir(date), exist_ok=True)
    path = _subject_file(date, subject_id)
    is_new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["roll_no", "name", "time", "status"])
        writer.writerow(row)


def mark_present(date, subject_id, roll_no, name):
    _append_subject_row(date, subject_id, [roll_no, name, datetime.now().strftime("%H:%M:%S"), "Present"])


def mark_absent(date, subject_id, roll_no, name):
    _append_subject_row(date, subject_id, [roll_no, name, "-", "Absent"])


def finalize_absentees(date, subject_id, eligible_rolls):
    """Marks every eligible (same branch+semester) student not yet recorded as Absent."""
    marked = {row[0] for row in read_subject_rows(date, subject_id)}
    labels = load_labels()
    count = 0
    for roll_no in eligible_rolls:
        if roll_no not in marked:
            mark_absent(date, subject_id, roll_no, labels.get(roll_no, {}).get("name", ""))
            count += 1
    return count


def is_finalized(date, subject_id):
    path = _finalized_file(date)
    if not os.path.exists(path):
        return False
    with open(path, "r") as f:
        return subject_id in json.load(f)


def mark_finalized(date, subject_id):
    path = _finalized_file(date)
    finalized = set()
    if os.path.exists(path):
        with open(path, "r") as f:
            finalized = set(json.load(f))
    finalized.add(subject_id)
    os.makedirs(_day_dir(date), exist_ok=True)
    with open(path, "w") as f:
        json.dump(sorted(finalized), f, indent=2)


# ---------------- report helpers (daily / weekly / monthly / semester) ----------------

def list_attendance_dates():
    """Every date (folder) that has at least one subject's attendance CSV, oldest first."""
    if not os.path.exists(config.ATTENDANCE_DIR):
        return []
    dates = []
    for name in os.listdir(config.ATTENDANCE_DIR):
        full = os.path.join(config.ATTENDANCE_DIR, name)
        if os.path.isdir(full) and any(f.endswith(".csv") for f in os.listdir(full)):
            dates.append(name)
    return sorted(dates)


def list_dates_for_subject(subject_id):
    """Dates where this particular subject has an attendance CSV, oldest first."""
    return [d for d in list_attendance_dates() if os.path.exists(_subject_file(d, subject_id))]

def list_dates_for_subjects(subject_ids):
    """Union of dates where ANY of these subjects has an attendance CSV, oldest first."""
    dates = set()
    for sid in subject_ids:
        dates.update(list_dates_for_subject(sid))
    return sorted(dates)


def list_subjects_recorded_on(date):
    """subject_ids that have a CSV for that date."""
    day_dir = _day_dir(date)
    if not os.path.exists(day_dir):
        return []
    return sorted(f[:-4] for f in os.listdir(day_dir) if f.endswith(".csv"))


def daily_counts(dates, subject_ids):
    """
    [(date, present_count, absent_count), ...] across the given dates, summed
    over every subject in subject_ids (pass a single-item list for one subject).
    """
    if isinstance(subject_ids, str):
        subject_ids = [subject_ids]
    result = []
    for date in dates:
        present = absent = 0
        for subject_id in subject_ids:
            rows = read_subject_rows(date, subject_id)
            present += sum(1 for r in rows if r[3] == "Present")
            absent += sum(1 for r in rows if r[3] == "Absent")
        result.append((date, present, absent))
    return result


def per_student_summary(dates, subject_ids, eligible_rolls=None):
    """
    Across the given dates and subjects (pass a single-item list for one
    subject, or several to aggregate "All Subjects"): how many times each
    student was Present out of how many lectures they have a recorded row
    for. If eligible_rolls is given, those students are pre-seeded with 0/0
    even if they were never marked (so zero-attendance students still show up).
    Returns {roll_no: {"name": ..., "present": int, "recorded": int}}.
    """
    if isinstance(subject_ids, str):
        subject_ids = [subject_ids]
    labels = load_labels()
    if eligible_rolls is not None:
        summary = {roll: {"name": labels.get(roll, {}).get("name", ""), "present": 0, "recorded": 0}
                   for roll in eligible_rolls}
    else:
        summary = {}
    for date in dates:
        for subject_id in subject_ids:
            rows = read_subject_rows(date, subject_id)
            for roll_no, name, time_str, status in rows:
                if roll_no not in summary:
                    summary[roll_no] = {"name": name, "present": 0, "recorded": 0}
                summary[roll_no]["recorded"] += 1
                if status == "Present":
                    summary[roll_no]["present"] += 1
    return summary