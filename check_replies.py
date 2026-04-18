"""Detect recruiter replies via IMAP (Gmail by default).

For each sent email, connects to the user's inbox and searches for messages
FROM the recipient address within the last N days (`imap.lookback_days`).
When a match is found, stores reply metadata under tracking["replies"].

Uses the same credentials as SMTP — Gmail app passwords work for both.
"""
import email
import imaplib
import json
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from config import load_config

BASE_DIR = Path(__file__).parent


def load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _decode(raw):
    """Decode an RFC 2047-encoded header (handles UTF-8/Latin-1/Base64)."""
    if not raw:
        return ""
    parts = []
    for piece, charset in decode_header(raw):
        if isinstance(piece, bytes):
            try:
                parts.append(piece.decode(charset or "utf-8", errors="replace"))
            except (LookupError, TypeError):
                parts.append(piece.decode("utf-8", errors="replace"))
        else:
            parts.append(piece)
    return "".join(parts).strip()


def _extract_preview(msg, limit=240):
    """Return the first ~240 chars of the plain-text body, stripped of quoted replies."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body = payload.decode(charset, errors="replace")
                    except (LookupError, TypeError):
                        body = payload.decode("utf-8", errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                body = payload.decode(charset, errors="replace")
            except (LookupError, TypeError):
                body = payload.decode("utf-8", errors="replace")

    # Strip quoted reply blocks (lines starting with ">", or everything after "On ... wrote:")
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if re.match(r"^(On|Le)\s.+(wrote|a écrit)\s*:\s*$", stripped):
            break
        lines.append(line)
    clean = "\n".join(lines).strip()
    return clean[:limit] + ("…" if len(clean) > limit else "")


def check_replies(config, on_progress=None, should_stop=None):
    """Scan INBOX for replies to previously sent emails.

    Returns counts and records the matches under tracking["replies"].
    Only checks companies that are in sent_emails and not yet in replies.
    """
    def emit(event_type, message, **extra):
        if on_progress:
            on_progress({"type": event_type, "message": message, **extra})
        else:
            print(f"[{event_type.upper()}] {message}")

    smtp = config["smtp"]
    imap = config.get("imap", {})
    server = imap.get("server") or "imap.gmail.com"
    port = int(imap.get("port") or 993)
    user = smtp.get("user")
    password = smtp.get("password")
    lookback_days = int(imap.get("lookback_days") or 60)

    if not user or not password:
        raise ValueError("Identifiants email manquants (utilisez la même config que SMTP).")

    files = config["files"]
    emails_path = BASE_DIR / files["generated_emails"]
    tracking_path = BASE_DIR / files["tracking"]

    emails = load_json(emails_path, [])
    tracking = load_json(tracking_path, {})
    tracking.setdefault("sent_emails", [])
    tracking.setdefault("replies", {})

    sent_set = set(tracking["sent_emails"])
    already_replied = set(tracking["replies"].keys())

    # Only recheck sent emails that don't yet have a recorded reply.
    queue = [e for e in emails
             if e.get("company_name") in sent_set
             and e.get("company_name") not in already_replied
             and e.get("hr_email")]

    counts = {"new_replies": 0, "checked": len(queue), "total_replies": len(tracking["replies"])}
    if not queue:
        emit("info", f"Aucun email à vérifier ({len(tracking['replies'])} réponses déjà connues).")
        emit("done", "Terminé.")
        return counts

    emit("info", f"Connexion à {server}:{port} en tant que {user}…")
    try:
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(user, password)
    except imaplib.IMAP4.error as e:
        raise ValueError(f"Connexion IMAP refusée : {e}")

    try:
        mail.select("INBOX")
        since = (datetime.now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")

        for idx, e in enumerate(queue, 1):
            if should_stop and should_stop():
                emit("cancelled", "Vérification annulée.")
                break

            company = e["company_name"]
            hr_email = (e.get("hr_email") or "").strip()

            # IMAP SEARCH with FROM + SINCE filter
            query = f'(FROM "{hr_email}" SINCE {since})'
            status, data = mail.search(None, query)

            if status != "OK" or not data or not data[0]:
                emit("info", f"[{idx}/{len(queue)}] {company} — aucune réponse")
                continue

            msg_ids = data[0].split()
            # Fetch the most recent matching message
            status, msg_data = mail.fetch(msg_ids[-1], "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                emit("info", f"[{idx}/{len(queue)}] {company} — lecture impossible")
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            # Prefer the original sender's date header; fall back to now.
            date_header = msg.get("Date", "")
            try:
                reply_dt = parsedate_to_datetime(date_header) if date_header else datetime.now(timezone.utc)
                reply_date_iso = reply_dt.isoformat()
            except (TypeError, ValueError):
                reply_date_iso = datetime.now(timezone.utc).isoformat()

            from_addr = parseaddr(msg.get("From", ""))[1] or hr_email

            tracking["replies"][company] = {
                "reply_date": reply_date_iso,
                "reply_subject": _decode(msg.get("Subject", "")),
                "reply_preview": _extract_preview(msg),
                "from": from_addr,
            }
            save_json(tracking_path, tracking)

            counts["new_replies"] += 1
            emit("success",
                 f"[{idx}/{len(queue)}] {company} — réponse détectée ({from_addr})",
                 company=company)

    finally:
        try:
            mail.logout()
        except Exception:
            pass

    counts["total_replies"] = len(tracking["replies"])
    emit("done",
         f"Vérification terminée. {counts['new_replies']} nouvelle(s) réponse(s) sur {counts['checked']} vérifiée(s).")
    return counts


def main():
    config = load_config()
    check_replies(config)


if __name__ == "__main__":
    main()
