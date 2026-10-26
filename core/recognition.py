"""
Face detection (Haar cascade) and the LBPH recognizer training/loading.
"""

import os
import cv2
import numpy as np

import config
from core import storage

face_cascade = cv2.CascadeClassifier(config.CASCADE_FILE)


def train_model():
    """Rebuilds trainer.yml from every image under dataset/<roll>_<name>/."""
    labels = storage.load_labels()
    faces, label_ids = [], []

    for folder_name in os.listdir(config.DATASET_DIR):
        folder_path = os.path.join(config.DATASET_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue
        parts = folder_name.split("_", 1)
        roll_no = parts[0]
        if roll_no not in labels:
            labels[roll_no] = {
                "label_id": storage.next_label_id(labels),
                "name": parts[1] if len(parts) > 1 else "",
                "branch": "", "semester": "", "email": "",
            }
        label_id = labels[roll_no]["label_id"]
        for img_name in os.listdir(folder_path):
            img = cv2.imread(os.path.join(folder_path, img_name), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                faces.append(img)
                label_ids.append(label_id)

    storage.save_labels(labels)
    if faces:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(faces, np.array(label_ids))
        recognizer.save(config.MODEL_FILE)
    elif os.path.exists(config.MODEL_FILE):
        os.remove(config.MODEL_FILE)

# ---------------- live matching helpers ----------------

def is_sharp_enough(face_gray):
    """False for blurry crops (motion blur / stream hiccups) - they hurt the trained model."""
    return cv2.Laplacian(face_gray, cv2.CV_64F).var() >= config.MIN_SHARPNESS


def rank_matches(recognizer, face_gray):
    """[(label_id, best_distance), ...] one entry per person, best match first."""
    collector = cv2.face.StandardCollector_create()
    recognizer.predict_collect(face_gray, collector)
    best = {}
    for label, dist in collector.getResults(True):
        if label not in best or dist < best[label]:
            best[label] = dist
    return sorted(best.items(), key=lambda kv: kv[1])


def pick_match(ranked, threshold=None, margin=None):
    """
    Decide who a face is. Returns (label_id or None, best_distance, runner_up_distance or None).
    A match needs a small enough distance AND a clear gap over the 2nd-best person,
    so two similar-looking people don't get swapped.
    """
    threshold = config.CONFIDENCE_THRESHOLD if threshold is None else threshold
    margin = config.MATCH_MARGIN if margin is None else margin
    if not ranked:
        return None, None, None
    label, best = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else None
    if best >= threshold:
        return None, best, runner_up
    if runner_up is not None and (runner_up - best) < margin:
        return None, best, runner_up
    return label, best, runner_up


class StreakTracker:
    """
    Marks someone as confirmed only after being matched in `needed` frames in a row.
    One misread frame can no longer write the wrong student as Present for the whole day.
    """

    def __init__(self, needed=None):
        self.needed = config.STABLE_FRAMES if needed is None else needed
        self.counts = {}

    def update(self, seen):
        """seen = set of ids matched in THIS frame. Returns the set confirmed so far."""
        for key in list(self.counts):
            if key not in seen:
                self.counts[key] = 0
        confirmed = set()
        for key in seen:
            self.counts[key] = self.counts.get(key, 0) + 1
            if self.counts[key] >= self.needed:
                confirmed.add(key)
        return confirmed

    def reset(self):
        self.counts = {}