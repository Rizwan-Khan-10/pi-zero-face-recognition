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
