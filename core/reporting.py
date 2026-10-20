"""
Pure report maths - no Tkinter, no matplotlib. The Report screen (ui/report.py)
calls these functions, so the numbers can be tested without opening the GUI.
"""

from core import storage


def pct(present, total):
    """Attendance percentage, or None when there is nothing recorded yet."""
    return (present / total * 100.0) if total else None


def parse_threshold(text, default=None):
    """'75', ' 75 %', '72.5' -> float. Anything invalid / outside 0-100 -> default."""
    try:
        value = float(str(text).strip().replace("%", ""))
    except ValueError:
        return default
    if value < 0 or value > 100:
        return default
    return value


def is_low(percent, threshold):
    """True when the student HAS data and is below the minimum."""
    return percent is not None and percent < threshold


def status_text(percent, threshold):
    if percent is None:
        return "No data"
    return "LOW" if percent < threshold else "OK"


def subject_code(subject_id, subjects=None):
    """Short column heading: the course code (ITC701) if the subject has one, else the name's first letters."""
    subjects = subjects if subjects is not None else storage.load_subjects()
    info = subjects.get(subject_id, {})
    return info.get("code") or info.get("name", subject_id)[:8]


def student_matrix(dates, subject_ids, eligible_rolls=None):
    """
    One row per student across the given dates + subjects:
      {"roll", "name", "present", "total", "pct",
       "per_subject": {subject_id: [present, total]}}
    eligible_rolls are pre-seeded so students with zero records still show up.
    Rows are sorted by name.
    """
    if isinstance(subject_ids, str):
        subject_ids = [subject_ids]
    labels = storage.load_labels()
    rows = {}

    def ensure(roll, name=""):
        if roll not in rows:
            rows[roll] = {
                "roll": roll,
                "name": name or labels.get(roll, {}).get("name", ""),
                "present": 0, "total": 0,
                "per_subject": {sid: [0, 0] for sid in subject_ids},
            }
        return rows[roll]

    for roll in (eligible_rolls or []):
        ensure(roll)

    for date in dates:
        for sid in subject_ids:
            for record in storage.read_subject_rows(date, sid):
                roll_no, name, _time, status = record[:4]
                row = ensure(roll_no, name)
                cell = row["per_subject"][sid]
                cell[1] += 1
                row["total"] += 1
                if status == "Present":
                    cell[0] += 1
                    row["present"] += 1

    result = list(rows.values())
    for row in result:
        row["pct"] = pct(row["present"], row["total"])
    result.sort(key=lambda r: (r["name"].lower(), r["roll"]))
    return result


def summary_stats(rows, threshold):
    """Counts for the summary cards: students / meeting minimum / below minimum / class average."""
    with_data = [r for r in rows if r["pct"] is not None]
    low = sum(1 for r in with_data if is_low(r["pct"], threshold))
    average = (sum(r["pct"] for r in with_data) / len(with_data)) if with_data else None
    return {
        "students": len(rows),
        "with_data": len(with_data),
        "low": low,
        "ok": len(with_data) - low,
        "average": average,
    }


def subject_averages(rows, subject_ids):
    """{subject_id: class-average % or None} - average of each student's own % in that subject."""
    result = {}
    for sid in subject_ids:
        values = [pct(r["per_subject"][sid][0], r["per_subject"][sid][1])
                  for r in rows if r["per_subject"].get(sid, [0, 0])[1]]
        result[sid] = (sum(values) / len(values)) if values else None
    return result


def histogram(rows, width=10):
    """[(low, high, count)] bands of overall % (the last band includes 100)."""
    bands = [[start, start + width, 0] for start in range(0, 100, width)]
    for r in rows:
        if r["pct"] is None:
            continue
        index = min(int(r["pct"] // width), len(bands) - 1)
        bands[index][2] += 1
    return [tuple(b) for b in bands]
