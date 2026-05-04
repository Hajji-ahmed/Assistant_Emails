"""Send generated emails via SMTP.

Two entry points:
- CLI: `python send_emails.py` (loads config from config.json)
- Programmatic: `send_all(config, on_progress=callback, only=[...])` for Flask routes
"""
import json
import smtplib
import ssl
import time
from datetime import date
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from config import load_config

BASE_DIR = Path(__file__).parent


def load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_message(sender_email, sender_name, recipient_name, recipient_email,
                  subject, body, resume_link):
    body_with_resume = body
    if resume_link:
        body_with_resume = f"{body}\n\nVous pouvez consulter le portfolio de notre équipe ici : {resume_link}"

    msg = MIMEText(body_with_resume, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = formataddr((sender_name, sender_email))
    msg['To'] = formataddr((recipient_name, recipient_email))
    return msg


def send_one(smtp_config, msg, recipient_email):
    """Return (success: bool, error: str|None)."""
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(smtp_config["server"], smtp_config["port"], context=context) as server:
            server.login(smtp_config["user"], smtp_config["password"])
            server.send_message(msg)
            return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check SMTP credentials."
    except smtplib.SMTPRecipientsRefused:
        return False, f"Recipient refused: {recipient_email}"
    except smtplib.SMTPSenderRefused:
        return False, "Sender address refused."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def _sleep_cancellable(seconds, should_stop):
    """Sleep in short slices so a cancel doesn't wait out the full delay."""
    if seconds <= 0:
        return False
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if should_stop and should_stop():
            return True
        time.sleep(min(0.2, end - time.monotonic()))
    return False


def send_all(config, on_progress=None, only=None, max_retries=3, should_stop=None):
    """Send every generated email that hasn't been sent yet.

    Args:
        config: dict from load_config()
        on_progress: optional callable(event: dict). Event types:
            "info", "success", "error", "skip", "done", "cancelled", "quota".
        only: optional iterable of company_name values. If provided, only
            those are considered (still skipped if already sent).
        max_retries: retries per email before aborting the whole run.
        should_stop: optional callable() -> bool. Returning True aborts at the
            next safe checkpoint (and shortens inter-send sleep).
    Returns:
        dict: {"sent": int, "failed": int, "skipped": int, "total": int}
    """
    def emit(event_type, message, **extra):
        if on_progress:
            on_progress({"type": event_type, "message": message, **extra})
        else:
            print(f"[{event_type.upper()}] {message}")

    smtp = config["smtp"]
    if not smtp.get("user") or not smtp.get("password"):
        raise ValueError("SMTP credentials missing in config.")

    profile = config["profile"]
    sender_name = profile.get("sender_display_name") or smtp.get("sender_name") or smtp["user"]
    resume_link = profile.get("resume_link", "")

    sending = config.get("sending", {})
    send_delay = float(sending.get("send_delay_seconds", 2))
    daily_limit = int(sending.get("daily_limit", 0))  # 0 = unlimited

    files = config["files"]
    emails_path = BASE_DIR / files["generated_emails"]
    tracking_path = BASE_DIR / files["tracking"]

    emails = load_json(emails_path, [])
    tracking = load_json(tracking_path, {})
    tracking.setdefault("sent_emails", [])
    tracking.setdefault("daily_counters", {})
    tracking.setdefault("sent_dates", {})
    today = date.today().isoformat()
    today_count = int(tracking["daily_counters"].get(today, 0))
    sent_set = set(tracking["sent_emails"])

    if only is not None:
        only_set = set(only)
        queue = [e for e in emails if e["company_name"] in only_set and e["company_name"] not in sent_set]
    else:
        queue = [e for e in emails if e["company_name"] not in sent_set]

    counts = {"sent": 0, "failed": 0, "skipped": len(emails) - len(queue), "total": len(queue)}
    emit("info", f"Queue: {len(queue)} emails (skipped {counts['skipped']} already sent).")
    if daily_limit > 0:
        remaining = max(0, daily_limit - today_count)
        emit("info", f"Cap quotidien: {today_count}/{daily_limit} envoyés aujourd'hui, {remaining} restants.")

    for idx, email_data in enumerate(queue, 1):
        if should_stop and should_stop():
            emit("cancelled", "Envoi annulé par l'utilisateur.")
            break

        if daily_limit > 0 and today_count >= daily_limit:
            emit("quota", f"Cap quotidien atteint ({daily_limit}). Arrêt du batch.")
            break

        if idx > 1 and send_delay > 0:
            if _sleep_cancellable(send_delay, should_stop):
                emit("cancelled", "Envoi annulé par l'utilisateur.")
                break

        company = email_data["company_name"]
        emit("info", f"[{idx}/{len(queue)}] Sending to {company}...", company=company)

        try:
            msg = build_message(
                sender_email=smtp["user"],
                sender_name=sender_name,
                recipient_name=email_data.get("hr_name", ""),
                recipient_email=email_data["hr_email"],
                subject=email_data["email_subject"],
                body=email_data["email_body"],
                resume_link=resume_link,
            )
        except KeyError as e:
            counts["failed"] += 1
            emit("error", f"Missing field for {company}: {e}", company=company)
            continue

        sent = False
        last_error = None
        for attempt in range(1, max_retries + 1):
            ok, err = send_one(smtp, msg, email_data["hr_email"])
            if ok:
                sent = True
                break
            last_error = err
            emit("info", f"Attempt {attempt}/{max_retries} failed for {company}: {err}", company=company)
            if attempt < max_retries:
                time.sleep(5 * attempt)

        if sent:
            from datetime import datetime, timezone
            tracking["sent_emails"].append(company)
            tracking["sent_dates"][company] = datetime.now(timezone.utc).isoformat()
            today_count += 1
            tracking["daily_counters"][today] = today_count
            save_json(tracking_path, tracking)
            counts["sent"] += 1
            emit("success", f"Sent to {company} ({today_count}{'/' + str(daily_limit) if daily_limit > 0 else ''} today)", company=company)
        else:
            counts["failed"] += 1
            emit("error", f"Failed to send to {company}: {last_error}", company=company)
            emit("info", "Stopping batch after repeated failures.")
            break

    emit("done", f"Send complete. Sent: {counts['sent']}, Failed: {counts['failed']}, Skipped: {counts['skipped']}")
    return counts


def main():
    config = load_config()
    send_all(config)


if __name__ == "__main__":
    main()
