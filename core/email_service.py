"""
Suggesting a college email for a new student, and sending attendance
status emails over Gmail SMTP.
"""

import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText

import config
from core import storage


def suggest_email(name, roll_no, branch):
    if not name or not roll_no or not branch:
        return ""
    first_name = name.strip().split()[0].lower()
    return f"{first_name}.{roll_no}.{branch.strip().lower()}@{config.COLLEGE_EMAIL_DOMAIN}"


def send_email(to_email, subject, body):
    """Returns (ok, error_message)."""
    if not to_email:
        return False, "This student has no email on file (add one in Manage Students)"
    if to_email.strip().lower().endswith(".invalid"):   # demo students - never leaves the laptop
        return False, "Demo address - not sent"
    if not config.SENDER_EMAIL or not config.SENDER_APP_PASSWORD:
        return False, "SENDER_EMAIL / SENDER_APP_PASSWORD not set in .env"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = config.SENDER_EMAIL
        msg["To"] = to_email
        context = ssl.create_default_context()
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(config.SENDER_EMAIL, config.SENDER_APP_PASSWORD)
            server.sendmail(config.SENDER_EMAIL, to_email, msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail login failed - wrong App Password (your normal Gmail password will not work)"
    except Exception as e:
        return False, str(e)


def send_lecture_emails(date_str, subject_id):
    """
    Emails every REAL student recorded for this subject+date their status.
    Demo (dummy) students are skipped - they are fake and must never get mail.
    Returns (sent_count, [failures], skipped_demo_count).
    """
    labels = storage.load_labels()
    rows = storage.read_subject_rows(date_str, subject_id)
    subject_name = storage.load_subjects().get(subject_id, {}).get("name", subject_id)
    sent, skipped, failures = 0, 0, []
    for roll_no, name, time_str, status in rows:
        info = labels.get(roll_no, {})
        if storage.is_demo(info):
            skipped += 1
            continue
        email = info.get("email", "")
        subject_line = f"Attendance - {subject_name} - {date_str}"
        body = (
            f"Dear {name},\n\n"
            f"Your attendance status for {subject_name} on {date_str} is: {status}.\n"
            + (f"Marked at: {time_str}\n" if status == "Present" else "")
            + "\nThis is an automated message from the Attendance System."
        )
        ok, err = send_email(email, subject_line, body)
        if ok:
            sent += 1
        else:
            failures.append(f"{name} ({roll_no}): {err}")
    return sent, failures, skipped
