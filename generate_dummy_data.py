"""
Demo data for the presentation: REAL students + DUMMY (demo) students side by side.

    python generate_dummy_data.py            full reset (asks before wiping existing attendance)
    python generate_dummy_data.py --yes      full reset without asking
    python generate_dummy_data.py --no-real-history
                                             full reset, but real students get no seeded history

What the full reset does
------------------------
* Keeps every REAL student - anyone who has a face folder in dataset/<roll>_<Name>/ -
  and puts them in IT / Sem 7 together with ~40 dummy students (no face data).
* EVERY student (real and dummy) is IT / Sem 7. Only the IT branch and its Mumbai University
  Sem 7 subjects (Rev-2019 'C' scheme) exist.
* Electives: the real students are all in CSL; the dummy students are split between CSL and DMMM.
* Wipes all old attendance and writes ~90 days of seeded history for Sem 7 (timetable based,
  Sundays + a few random holidays skipped). Today is left empty so the live camera
  demo marks real students on a clean day.
* Retrains the face model so the label ids match labels.json.

Dummy students are flagged "demo": true in labels.json and use the reserved ".invalid" e-mail
domain, so lecture e-mails are never sent to them (the e-mail code skips them as well).

When you take REAL attendance later (any subject) and press Finalize, every student who was not
scanned - i.e. all the dummy students - is marked Absent automatically. Nothing else to run.
"""

import argparse
import csv
import json
import os
import random
import re
import shutil
from datetime import datetime, timedelta

import config
from core import storage

BRANCH, SEMESTER = "IT", "7"
random.seed(42)

NUM_DUMMY = 40
DAYS_OF_HISTORY = 90
HOLIDAY_CHANCE = 0.08          # random no-lecture days (besides Sundays)
DUMMY_EMAIL_DOMAIN = config.DEMO_EMAIL_DOMAIN   # reserved ".invalid" - can never receive mail

# Seeded history for the REAL students too, so the report shows them next to the dummies.
# Their rates are kept high on purpose; use --no-real-history to skip it.
REAL_STUDENT_RATE = (0.86, 0.96)

# University of Mumbai, B.E. Information Technology, Semester VII (Rev-2019 'C' scheme).
# Our class: DLO-4 = Information Retrieval System (IRS); Institute Optional-1 is split in two groups -
# some students take Cyber Security and Laws (CSL), the others Disaster Management and Mitigation Measures (DMMM).
# DLO-3 (Software Testing and QA) is one common pick - rename it in Manage Subjects if yours differs.
# (code / short name shown in the report, name, weekdays [Mon=0 .. Sat=5], lecture start hour)
SUBJECTS = [
    ("ITC701",   "AI and DS - II",                       (0, 2, 4), 9),
    ("ITC702",   "Internet of Everything",               (1, 3, 5), 9),
    ("ITDO7014", "Software Testing and QA",              (0, 2, 4), 11),
    ("IRS",      "Information Retrieval System",         (1, 3, 5), 11),
    ("CSL",      "Cyber Security and Laws",              (2, 4),    14),
    ("DMMM",     "Disaster Management and Mitigation Measures", (2, 4), 14),
    ("ITL701",   "Data Science Lab",                     (0,),      14),
    ("ITL702",   "IoE Lab",                              (1,),      14),
    ("ITL703",   "Secure Application Development Lab",  (3,),      14),
    ("ITL704",   "Recent Open Source Project Lab",       (5,),      14),
]

# Subjects only some students take. Real students are all in CSL; the dummies are split between CSL and DMMM.
ELECTIVE_CODES = ("CSL", "DMMM")
REAL_ELECTIVE = "CSL"
CSL_SHARE = 0.5          # share of the DUMMY students that take CSL (the rest take DMMM)

FIRST_NAMES = ["Aisha", "Rohan", "Priya", "Aman", "Sneha", "Vikram", "Neha", "Karan", "Divya", "Arjun",
               "Pooja", "Sahil", "Meera", "Yash", "Riya", "Tarun", "Anjali", "Rahul", "Simran", "Zoya",
               "Faizan", "Sana", "Imran", "Kabir", "Ayesha", "Dev", "Nikhil", "Tanvi", "Mohsin", "Alina"]
LAST_NAMES = ["Verma", "Sharma", "Patel", "Singh", "Gupta", "Mehta", "Joshi", "Reddy", "Nair", "Chauhan",
              "Kapoor", "Bhatt", "Pillai", "Rao", "Shaikh", "Ansari", "Siddiqui", "Qureshi", "Deshmukh", "Khan"]

ROLL_START = 991001   # dummy roll numbers use a separate 99xxxx range, so they can never clash with real students added later (23xxxx)


# ---------------------------------------------------------------- students

def find_real_students():
    """{roll_no: name} from the face folders in dataset/ (<roll>_<Name>)."""
    real = {}
    if os.path.isdir(config.DATASET_DIR):
        for folder in sorted(os.listdir(config.DATASET_DIR)):
            if os.path.isdir(os.path.join(config.DATASET_DIR, folder)):
                match = re.match(r"^(\d+)_(.+)$", folder)
                if match:
                    real[match.group(1)] = match.group(2).strip()
    return real


def _sid(code):
    name = next(n for c, n, _d, _h in SUBJECTS if c == code)
    return storage.make_subject_id(BRANCH, SEMESTER, name)


def make_students(real, old_labels):
    """Real students first (keeping their old label_id / e-mail when they had one), then dummies."""
    labels, used_ids = {}, set()

    def next_id():
        i = 0
        while i in used_ids:
            i += 1
        used_ids.add(i)
        return i

    for roll, name in real.items():
        old = old_labels.get(roll, {})
        label_id = old.get("label_id")
        if label_id is None or label_id in used_ids:
            label_id = next_id()
        else:
            used_ids.add(label_id)
        email = old.get("email") or f"{name.split()[0].lower()}.{roll}.{BRANCH.lower()}@{config.COLLEGE_EMAIL_DOMAIN}"
        electives = old.get("electives") or [_sid(REAL_ELECTIVE)]
        labels[roll] = {"label_id": label_id, "name": old.get("name") or name,
                        "branch": BRANCH, "semester": SEMESTER, "email": email, "electives": electives}

    taken_names = {n.lower() for n in real.values()}
    # shuffled CSL/DMMM list so the split is even (not left to chance) and the dummies are mixed up
    dummy_electives = ["CSL"] * round(NUM_DUMMY * CSL_SHARE)
    dummy_electives += ["DMMM"] * (NUM_DUMMY - len(dummy_electives))
    random.shuffle(dummy_electives)
    roll_no = ROLL_START
    while len(labels) < len(real) + NUM_DUMMY:
        roll = str(roll_no)
        roll_no += 1
        if roll in labels:
            continue
        while True:
            name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            if name.lower() not in taken_names:
                taken_names.add(name.lower())
                break
        labels[roll] = {"label_id": next_id(), "name": name, "branch": BRANCH, "semester": SEMESTER,
                        "email": f"{name.split()[0].lower()}.{roll}.{BRANCH.lower()}@{DUMMY_EMAIL_DOMAIN}",
                        "electives": [_sid(dummy_electives.pop())], "demo": True}
    return labels


def make_subjects():
    subjects = {}
    for code, name, _days, _hour in SUBJECTS:
        subjects[storage.make_subject_id(BRANCH, SEMESTER, name)] = {
            "name": name, "branch": BRANCH, "semester": SEMESTER, "code": code}
        if code in ELECTIVE_CODES:
            subjects[storage.make_subject_id(BRANCH, SEMESTER, name)]["elective"] = True
    return subjects


# ---------------------------------------------------------------- attendance

def _write_csv(day_dir, subject_id, rows):
    os.makedirs(day_dir, exist_ok=True)
    with open(os.path.join(day_dir, f"{subject_id}.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["roll_no", "name", "time", "status"])
        writer.writerows(rows)


def _attendance_rates(labels, real, seed_real):
    """Per-student base probability. A few students are clearly short (<75%) and a few sit near the
    line, so changing the minimum live in the report visibly moves people between green and red."""
    dummies = [r for r in labels if r not in real]
    low = set(random.sample(dummies, k=max(4, len(dummies) // 7)))
    border = set(random.sample([r for r in dummies if r not in low], k=4))
    rate = {}
    for roll in labels:
        if roll in real:
            rate[roll] = random.uniform(*REAL_STUDENT_RATE) if seed_real else None
        elif roll in low:
            rate[roll] = random.uniform(0.45, 0.68)
        elif roll in border:
            rate[roll] = random.uniform(0.73, 0.79)
        else:
            rate[roll] = random.uniform(0.82, 0.97)
    return rate


def _lecture_rows(rolls, labels, rate, hour, is_lab):
    rows = []
    for roll in rolls:
        p = min(0.99, max(0.05, rate[roll] + random.gauss(0, 0.05) + (0.03 if is_lab else 0)))
        if random.random() < p:
            rows.append([roll, labels[roll]["name"],
                         f"{hour:02d}:{random.randint(0, 25):02d}:{random.randint(0, 59):02d}", "Present"])
        else:
            rows.append([roll, labels[roll]["name"], "-", "Absent"])
    return rows


def make_history(labels, subjects, real, seed_real):
    rate = _attendance_rates(labels, real, seed_real)
    rolls = [r for r in labels if rate[r] is not None]
    sid_for = {code: storage.make_subject_id(BRANCH, SEMESTER, name) for code, name, _d, _h in SUBJECTS}
    today = datetime.now().date()
    days = 0
    for days_ago in range(DAYS_OF_HISTORY, 0, -1):
        day = today - timedelta(days=days_ago)
        if day.weekday() == 6 or (days_ago > 7 and random.random() < HOLIDAY_CHANCE):   # last week always has classes
            continue
        held = []
        day_dir = os.path.join(config.ATTENDANCE_DIR, day.strftime("%Y-%m-%d"))
        for code, name, weekdays, hour in SUBJECTS:
            if day.weekday() not in weekdays:
                continue
            sid = sid_for[code]
            attending = [r for r in rolls if code not in ELECTIVE_CODES or sid in labels[r]["electives"]]
            _write_csv(day_dir, sid, _lecture_rows(attending, labels, rate, hour, code.startswith("ITL")))
            held.append(sid)
        if held:
            with open(os.path.join(day_dir, "finalized.json"), "w") as f:
                json.dump(sorted(held), f, indent=2)
            days += 1
    return days


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Create real + dummy demo data (IT, Sem 7).")
    parser.add_argument("--no-real-history", action="store_true",
                        help="don't seed past attendance for the real students")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="don't ask before wiping existing attendance")
    args = parser.parse_args()

    if not args.yes and os.path.isdir(config.ATTENDANCE_DIR) and os.listdir(config.ATTENDANCE_DIR):
        print("This will DELETE everything in attendance/ (including attendance taken with the camera) "
              "and rebuild the demo data.")
        if input("Type YES to continue: ").strip() != "YES":
            print("Cancelled - nothing was changed.")
            return

    real = find_real_students()
    old_labels = storage.load_labels()

    if os.path.exists(config.ATTENDANCE_DIR):
        shutil.rmtree(config.ATTENDANCE_DIR)
    os.makedirs(config.ATTENDANCE_DIR, exist_ok=True)
    os.makedirs(config.DATASET_DIR, exist_ok=True)

    labels = make_students(real, old_labels)
    storage.save_labels(labels)
    storage.save_branches([BRANCH])
    subjects = make_subjects()
    storage.save_subjects(subjects)
    days = make_history(labels, subjects, real, seed_real=not args.no_real_history)

    try:
        from core.recognition import train_model
        train_model()
        trained = "face model retrained"
    except Exception as e:   # e.g. opencv-contrib not installed on this machine
        trained = f"face model NOT retrained ({e}) - open the app once / re-run after installing opencv-contrib-python"

    csl, dmmm = _sid("CSL"), _sid("DMMM")
    print(f"Real students kept   : {len(real)}  ({', '.join(f'{n} {r}' for r, n in real.items()) or 'none'})")
    print(f"Dummy students added : {len(labels) - len(real)}  (all {BRANCH} / Sem {SEMESTER}, e-mails @{DUMMY_EMAIL_DOMAIN} - never mailed)")
    print(f"Branch / semester    : {BRANCH} / Sem {SEMESTER}  |  subjects: {len(subjects)} (Mumbai University Rev-2019 'C')")
    print(f"Electives            : CSL {sum(1 for v in labels.values() if csl in v['electives'])} students "
          f"({sum(1 for r in real if csl in labels[r]['electives'])} real), "
          f"DMMM {sum(1 for v in labels.values() if dmmm in v['electives'])} students "
          f"({sum(1 for r in real if dmmm in labels[r]['electives'])} real)")
    print(f"Attendance history   : {days} class days (last {DAYS_OF_HISTORY} days, today left empty)")
    print(f"{trained}")
    print("\nDummy students have no face data - only the real ones are recognised by the camera.")
    print("When you take real attendance and press Finalize, every student who was not scanned (= all dummies) is marked Absent.")


if __name__ == "__main__":
    main()
