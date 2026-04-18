"""Generate and send follow-up emails to recipients who didn't reply.

Candidates:
  * in tracking["sent_dates"] with elapsed days >= followups.delay_days
  * NOT in tracking["replies"]
  * NOT already in tracking["followups_sent"]

For each candidate we:
  1. Load the active followup template (config.prompts.active_followup)
  2. Render it with the corresponding startup record (via startups.json lookup)
  3. Call OpenAI to produce subject + body
  4. Send via the same SMTP path as send_emails
  5. Record timestamp in tracking["followups_sent"]
"""
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from openai import OpenAI

from config import load_config
from send_emails import (
    load_json, save_json, build_message, send_one, _sleep_cancellable,
)
from generate_emails import render_prompt, parse_email_response
from templates_mgr import load_body, get_meta

BASE_DIR = Path(__file__).parent


def _load_startups_index(path: Path) -> dict:
    """Return {EntrepriseName: full_startup_record} for quick lookup."""
    data = load_json(path, {"data": []})
    items = data.get("data", []) if isinstance(data, dict) else data
    return {s.get("EntrepriseName"): s for s in items if s.get("EntrepriseName")}


def find_due_followups(config, now=None):
    """Return the list of (email_record, days_elapsed) tuples that are due.
    Pure function — no side effects."""
    now = now or datetime.now(timezone.utc)
    delay_days = int(config.get("followups", {}).get("delay_days") or 7)

    files = config["files"]
    tracking = load_json(BASE_DIR / files["tracking"], {})
    emails = load_json(BASE_DIR / files["generated_emails"], [])

    sent_dates = tracking.get("sent_dates") or {}
    replies = tracking.get("replies") or {}
    already_followed = set((tracking.get("followups_sent") or {}).keys())

    due = []
    for e in emails:
        company = e.get("company_name")
        if not company or company in replies or company in already_followed:
            continue
        sent_iso = sent_dates.get(company)
        if not sent_iso:
            continue
        try:
            sent_dt = datetime.fromisoformat(sent_iso)
            if sent_dt.tzinfo is None:
                sent_dt = sent_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        elapsed = (now - sent_dt).days
        if elapsed >= delay_days:
            due.append((e, elapsed))
    return due


def send_followups(config, on_progress=None, should_stop=None):
    """Generate + send follow-ups for every due company."""
    def emit(event_type, message, **extra):
        if on_progress:
            on_progress({"type": event_type, "message": message, **extra})
        else:
            print(f"[{event_type.upper()}] {message}")

    smtp = config["smtp"]
    if not smtp.get("user") or not smtp.get("password"):
        raise ValueError("Identifiants SMTP manquants.")
    if not config["openai"].get("api_key"):
        raise ValueError("Clé OpenAI manquante.")

    profile = config["profile"]
    sender_name = profile.get("sender_display_name") or smtp["user"]
    resume_link = profile.get("resume_link", "")
    signature = profile.get("signature", "")

    sending = config.get("sending", {})
    send_delay = float(sending.get("send_delay_seconds", 2))
    daily_limit = int(sending.get("daily_limit", 0))

    followup_id = config.get("prompts", {}).get("active_followup")
    if not followup_id or not get_meta(config, followup_id):
        raise ValueError("Aucun template de relance actif (voir /prompt).")
    template_body = load_body(config, followup_id)

    files = config["files"]
    tracking_path = BASE_DIR / files["tracking"]
    tracking = load_json(tracking_path, {})
    tracking.setdefault("followups_sent", {})
    tracking.setdefault("sent_dates", {})
    tracking.setdefault("daily_counters", {})

    today = date.today().isoformat()
    today_count = int(tracking["daily_counters"].get(today, 0))

    # Rebuild "due" list — don't rely on outside caller to filter
    due = find_due_followups(config)
    counts = {"sent": 0, "failed": 0, "skipped_quota": 0, "total": len(due)}

    emit("info", f"{len(due)} relance(s) due(s).")
    if not due:
        emit("done", "Aucune relance à envoyer.")
        return counts

    startups_index = _load_startups_index(BASE_DIR / files["startups"])
    openai_client = OpenAI(api_key=config["openai"]["api_key"])
    model = config["openai"]["model"]
    temperature = float(config["openai"].get("temperature", 0.2))
    max_tokens = int(config["openai"].get("max_tokens", 500))

    for idx, (email_record, elapsed) in enumerate(due, 1):
        if should_stop and should_stop():
            emit("cancelled", "Relances annulées.")
            break

        company = email_record["company_name"]
        hr_email = email_record.get("hr_email")
        if not hr_email:
            emit("skip", f"{company} — email destinataire manquant")
            continue

        if daily_limit > 0 and today_count >= daily_limit:
            emit("quota", f"Cap quotidien atteint ({daily_limit}).")
            counts["skipped_quota"] = len(due) - idx + 1
            break

        if idx > 1 and send_delay > 0:
            if _sleep_cancellable(send_delay, should_stop):
                emit("cancelled", "Relances annulées pendant la pause.")
                break

        startup = startups_index.get(company, {})
        prompt = render_prompt(template_body, startup, signature)
        emit("info", f"[{idx}/{len(due)}] {company} — génération (relance J+{elapsed})")

        try:
            resp = openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = (resp.choices[0].message.content or "").strip()
            subject, body = parse_email_response(text)
        except Exception as e:
            counts["failed"] += 1
            emit("error", f"{company} — échec génération : {e}", company=company)
            continue

        msg = build_message(
            sender_email=smtp["user"],
            sender_name=sender_name,
            recipient_name=email_record.get("hr_name", ""),
            recipient_email=hr_email,
            subject=subject,
            body=body,
            resume_link=resume_link,
        )
        ok, err = send_one(smtp, msg, hr_email)
        if ok:
            today_count += 1
            tracking["daily_counters"][today] = today_count
            tracking["followups_sent"][company] = {
                "sent_date": datetime.now(timezone.utc).isoformat(),
                "subject": subject,
                "body_preview": body[:240] + ("…" if len(body) > 240 else ""),
                "template_id": followup_id,
            }
            save_json(tracking_path, tracking)
            counts["sent"] += 1
            emit("success", f"{company} — relance envoyée", company=company)
        else:
            counts["failed"] += 1
            emit("error", f"{company} — échec envoi : {err}", company=company)

    emit("done", f"Terminé. {counts['sent']} relance(s) envoyée(s), {counts['failed']} échec(s).")
    return counts


def main():
    config = load_config()
    send_followups(config)


if __name__ == "__main__":
    main()
