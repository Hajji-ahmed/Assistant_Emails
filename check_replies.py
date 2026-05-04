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
    startups_path = BASE_DIR / files["startups"]

    emails = load_json(emails_path, [])
    tracking = load_json(tracking_path, {})
    tracking.setdefault("sent_emails", [])
    tracking.setdefault("replies", {})

    # Build a lookup of company_name -> hr_email from startups.json so we can
    # still check replies for companies whose generated email was deleted.
    startups_data = load_json(startups_path, {"data": []})
    startups_list = startups_data.get("data", []) if isinstance(startups_data, dict) else startups_data
    startup_by_name = {}
    for s in startups_list:
        name = s.get("EntrepriseName") or s.get("name") or ""
        email_addr = s.get("EntrepriseContactEmail") or s.get("email") or ""
        if name and email_addr:
            startup_by_name[name] = email_addr

    sent_set = set(tracking["sent_emails"])
    already_replied = set(tracking["replies"].keys())

    # First queue: companies that still have a generated email with hr_email.
    queue = [e for e in emails
             if e.get("company_name") in sent_set
             and e.get("company_name") not in already_replied
             and e.get("hr_email")]
    known_in_queue = {e["company_name"] for e in queue}

    # Second pass: companies sent but missing from generated_emails.json.
    # Use startups.json to recover the hr_email.
    orphaned = 0
    for company in sent_set - already_replied - known_in_queue:
        hr = startup_by_name.get(company)
        if hr:
            queue.append({"company_name": company, "hr_email": hr, "_from_startups": True})
            orphaned += 1

    if orphaned:
        emit("info", f"{orphaned} entreprise(s) retrouvée(s) via startups.json (email généré supprimé).")

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

    # Try Gmail's "All Mail" first (contains everything, including archived).
    # Falls back to INBOX for non-Gmail IMAP.
    folders_to_try = ['"[Gmail]/All Mail"', '"[Gmail]/Tous les messages"', "INBOX"]
    selected_folder = None
    for f in folders_to_try:
        status, _ = mail.select(f, readonly=True)
        if status == "OK":
            selected_folder = f
            break
    if not selected_folder:
        raise ValueError("Impossible d'ouvrir INBOX ou All Mail.")

    emit("info", f"Dossier sélectionné : {selected_folder}")

    # Quick sanity check — count all emails in lookback window so user can
    # confirm IMAP actually sees recent mail.
    try:
        since_check = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
        status, d = mail.search(None, f'(SINCE {since_check})')
        if status == "OK" and d and d[0]:
            total = len(d[0].split())
            emit("info", f"Sanity check : {total} email(s) reçu(s) depuis 30 jours dans ce dossier.")
            # Show the 5 most recent senders as a further sanity
            if total > 0:
                last_ids = d[0].split()[-5:]
                senders = []
                for mid in last_ids:
                    st, md = mail.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
                    if st == "OK" and md and md[0]:
                        raw = md[0][1].decode('utf-8', errors='ignore')
                        senders.append(raw.replace('From:', '').strip()[:60])
                emit("info", f"5 derniers expéditeurs : {senders}")
        else:
            emit("info", "Sanity check : 0 email sur les 30 derniers jours (anormal).")
    except Exception as diag_err:
        emit("info", f"Sanity check échoué : {diag_err}")

    try:
        since = (datetime.now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")

        # Automated senders to ignore (bounces, noreply, postmaster…)
        IGNORED_LOCAL_PARTS = ("noreply", "no-reply", "mailer-daemon",
                                "postmaster", "bounce", "notifications",
                                "donotreply", "do-not-reply")

        for idx, e in enumerate(queue, 1):
            if should_stop and should_stop():
                emit("cancelled", "Vérification annulée.")
                break

            company = e["company_name"]
            hr_email = (e.get("hr_email") or "").strip()

            # Match by DOMAIN instead of exact address so a reply from
            # marie@acme.ma counts as a reply to contact@acme.ma.
            # Falls back to the full address if it has no @.
            domain = hr_email.split("@", 1)[1].lower() if "@" in hr_email else hr_email

            # Skip pathological public-mailbox domains that would over-match
            # (unlikely a startup uses these, but guard anyway).
            if domain in ("gmail.com", "yahoo.fr", "yahoo.com", "hotmail.com",
                          "outlook.com", "outlook.fr", "live.fr"):
                query = f'(FROM "{hr_email}" SINCE {since})'
                search_hint = hr_email
            else:
                query = f'(FROM "@{domain}" SINCE {since})'
                search_hint = f"@{domain}"

            status, data = mail.search(None, query)

            if status != "OK" or not data or not data[0]:
                emit("info", f"[{idx}/{len(queue)}] {company} — aucune réponse (cherché: {search_hint})")
                continue

            match_count = len(data[0].split())
            emit("info", f"[{idx}/{len(queue)}] {company} — {match_count} message(s) depuis {search_hint}")

            # Walk matches newest-first and pick the first non-automated sender
            # that isn't the user themselves.
            msg_ids = data[0].split()
            chosen_msg = None
            chosen_from = None
            for mid in reversed(msg_ids):
                status, msg_data = mail.fetch(mid, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                m = email.message_from_bytes(msg_data[0][1])
                f_addr = parseaddr(m.get("From", ""))[1].lower()
                if not f_addr:
                    continue
                local = f_addr.split("@", 1)[0]
                # Skip bots and own address (in case Gmail echoes Sent here)
                if any(local.startswith(p) for p in IGNORED_LOCAL_PARTS):
                    continue
                if f_addr == user.lower():
                    continue
                chosen_msg = m
                chosen_from = f_addr
                break

            if not chosen_msg:
                emit("info", f"[{idx}/{len(queue)}] {company} — aucune réponse humaine")
                continue

            date_header = chosen_msg.get("Date", "")
            try:
                reply_dt = parsedate_to_datetime(date_header) if date_header else datetime.now(timezone.utc)
                reply_date_iso = reply_dt.isoformat()
            except (TypeError, ValueError):
                reply_date_iso = datetime.now(timezone.utc).isoformat()

            tracking["replies"][company] = {
                "reply_date": reply_date_iso,
                "reply_subject": _decode(chosen_msg.get("Subject", "")),
                "reply_preview": _extract_preview(chosen_msg),
                "from": chosen_from,
            }
            save_json(tracking_path, tracking)

            counts["new_replies"] += 1
            emit("success",
                 f"[{idx}/{len(queue)}] {company} — réponse détectée ({chosen_from})",
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
