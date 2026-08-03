
"""Flask entrypoint for the Internship Email Campaign Manager.

Phase 3: dashboard + config + prompt editor + startups + emails pages.
Generation/send actions come in Phase 4.
"""
import json
from pathlib import Path
from queue import Empty
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, Response

from config import load_config, save_config, detect_env_drift
from generate_emails import load_prompt_template, render_prompt, generate_all
from templates_mgr import (
    ensure_prompts_layout, list_templates, get_meta, load_body, save_body,
    create_template, delete_template, rename_template,
)
from startups_import import (
    parse_file as parse_startups_file,
    detect_mapping, map_row, merge_at_top, extract_from_email,
)
from send_emails import send_all, build_message, send_one
from send_followups import send_followups, find_due_followups
from check_replies import check_replies
from jobs import job_manager

BASE_DIR = Path(__file__).parent

# Status pipeline — order matters for display and progression semantics.
# "auto" statuses (draft/sent/replied) are derived from tracking; the others
# require a manual override stored in tracking["statuses"].
STATUS_ORDER = ["draft", "sent", "replied", "interview", "offer", "rejected", "abandoned"]
STATUS_LABELS = {
    "draft":     "Brouillon",
    "sent":      "Envoyé",
    "replied":   "Répondu",
    "interview": "Entretien",
    "offer":     "Offre",
    "rejected":  "Refus",
    "abandoned": "Abandonné",
}
AUTO_STATUSES = {"draft", "sent", "replied"}


def resolve_status(company: str, tracking: dict) -> tuple[str, bool]:
    """Return (status, is_manual). Manual overrides take precedence; otherwise
    the status is auto-derived from sent/replies lists.
    """
    manual = (tracking.get("statuses") or {}).get(company)
    if manual and manual in STATUS_LABELS:
        return manual, True
    if company in (tracking.get("replies") or {}):
        return "replied", False
    if company in (tracking.get("sent_emails") or []):
        return "sent", False
    return "draft", False

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = "dev-secret-change-in-production"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB limit on uploads

# Seed default + followup prompt templates on import (idempotent)
ensure_prompts_layout()


def safe_load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def resolve(relative_name: str) -> Path:
    return BASE_DIR / relative_name


def compute_stats(cfg: dict) -> dict:
    from datetime import date
    files = cfg["files"]
    startups = safe_load_json(resolve(files["startups"]), {"data": []})
    emails = safe_load_json(resolve(files["generated_emails"]), [])
    tracking = safe_load_json(resolve(files["tracking"]), {})
    today = date.today().isoformat()
    today_sent = int(tracking.get("daily_counters", {}).get(today, 0))
    daily_limit = int(cfg.get("sending", {}).get("daily_limit", 0))
    status_counts = {s: 0 for s in STATUS_ORDER}
    for e in emails:
        status, _ = resolve_status(e.get("company_name"), tracking)
        status_counts[status] += 1

    followups_sent = len(tracking.get("followups_sent", {}))
    try:
        followups_due = len(find_due_followups(cfg))
    except Exception:
        followups_due = 0

    return {
        "startups_total": len(startups.get("data", []) if isinstance(startups, dict) else startups),
        "emails_generated": len(emails),
        "emails_sent": len(tracking.get("sent_emails", [])),
        "companies_processed": len(tracking.get("processed_companies", [])),
        "today_sent": today_sent,
        "daily_limit": daily_limit,
        "replies_count": len(tracking.get("replies", {})),
        "status_counts": status_counts,
        "followups_sent": followups_sent,
        "followups_due": followups_due,
        "followups_delay_days": int(cfg.get("followups", {}).get("delay_days") or 7),
    }


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

@app.route("/")
def dashboard():
    cfg = load_config()
    return render_template(
        "dashboard.html",
        stats=compute_stats(cfg),
        cfg=cfg,
        status_order=STATUS_ORDER,
        status_labels=STATUS_LABELS,
    )


@app.route("/config", methods=["GET", "POST"])
def config_page():
    cfg = load_config()
    if request.method == "POST":
        form = request.form

        cfg["openai"]["api_key"] = form.get("openai_api_key", "").strip()
        cfg["openai"]["model"] = form.get("openai_model", "gpt-4o-mini").strip()
        cfg["openai"]["temperature"] = float(form.get("openai_temperature", 0.2) or 0.2)
        cfg["openai"]["max_tokens"] = int(form.get("openai_max_tokens", 500) or 500)

        cfg["smtp"]["user"] = form.get("smtp_user", "").strip()
        smtp_password = form.get("smtp_password", "")
        # Empty password field means "keep current" (avoids wiping on edit)
        if smtp_password:
            cfg["smtp"]["password"] = smtp_password
        cfg["smtp"]["server"] = form.get("smtp_server", "smtp.gmail.com").strip()
        cfg["smtp"]["port"] = int(form.get("smtp_port", 465) or 465)

        cfg["profile"]["sender_display_name"] = form.get("sender_display_name", "").strip()
        cfg["profile"]["resume_link"] = form.get("resume_link", "").strip()
        cfg["profile"]["phone"] = form.get("phone", "").strip()
        cfg["profile"]["linkedin"] = form.get("linkedin", "").strip()
        cfg["profile"]["github"] = form.get("github", "").strip()
        cfg["profile"]["signature"] = form.get("signature", "")

        cfg.setdefault("sending", {})
        cfg["sending"]["send_delay_seconds"] = float(form.get("send_delay_seconds", 2) or 2)
        cfg["sending"]["daily_limit"] = int(form.get("daily_limit", 0) or 0)

        save_config(cfg)
        flash("Configuration enregistrée.", "success")
        return redirect(url_for("config_page"))

    return render_template("config.html", cfg=cfg, drift=detect_env_drift(cfg))


@app.route("/prompt", methods=["GET"])
@app.route("/prompt/<template_id>", methods=["GET"])
def prompt_page(template_id=None):
    cfg = load_config()
    templates = list_templates(cfg)
    if not templates:
        ensure_prompts_layout()
        cfg = load_config()
        templates = list_templates(cfg)

    # Resolve selected template
    selected_id = template_id or request.args.get("id") or cfg["prompts"].get("active") or templates[0]["id"]
    meta = get_meta(cfg, selected_id)
    if not meta:
        meta = templates[0]
        selected_id = meta["id"]

    template_text = load_body(cfg, selected_id)

    startups = safe_load_json(resolve(cfg["files"]["startups"]), {"data": []}).get("data", [])
    sample_startup = startups[0] if startups else {}
    available_vars = sorted(set(sample_startup.keys()) | {"Signature"})

    return render_template(
        "prompt.html",
        templates=templates,
        selected=meta,
        template_text=template_text,
        available_vars=available_vars,
        sample_startup=sample_startup,
        active_campaign=cfg["prompts"].get("active"),
        active_followup=cfg["prompts"].get("active_followup"),
    )


@app.route("/api/templates", methods=["GET", "POST"])
def api_templates():
    cfg = load_config()
    if request.method == "GET":
        return jsonify({"templates": list_templates(cfg)})
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    kind = payload.get("kind") or "campaign"
    body = payload.get("body") or ""
    if not name:
        return jsonify({"ok": False, "error": "Nom requis."}), 400
    if kind not in ("campaign", "followup"):
        return jsonify({"ok": False, "error": "Kind invalide."}), 400
    meta = create_template(cfg, name, kind, body)
    return jsonify({"ok": True, "template": meta})


@app.route("/api/templates/<template_id>", methods=["PUT", "DELETE"])
def api_template_detail(template_id):
    cfg = load_config()
    if request.method == "DELETE":
        if delete_template(cfg, template_id):
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Template introuvable."}), 404

    payload = request.get_json(silent=True) or {}
    if "body" in payload:
        try:
            save_body(cfg, template_id, payload["body"])
        except KeyError as e:
            return jsonify({"ok": False, "error": str(e)}), 404
    if "name" in payload:
        rename_template(cfg, template_id, payload["name"])
    return jsonify({"ok": True})


@app.route("/api/templates/<template_id>/activate", methods=["POST"])
def api_template_activate(template_id):
    """Mark a template as the active one for its kind."""
    cfg = load_config()
    meta = get_meta(cfg, template_id)
    if not meta:
        return jsonify({"ok": False, "error": "Template introuvable."}), 404
    key = "active_followup" if meta["kind"] == "followup" else "active"
    cfg["prompts"][key] = template_id
    save_config(cfg)
    return jsonify({"ok": True, "active": {key: template_id}})


@app.route("/prompt/preview", methods=["POST"])
def prompt_preview():
    cfg = load_config()
    body = request.get_json(silent=True) or {}
    template_text = body.get("template", "")
    idx = int(body.get("startup_index", 0) or 0)

    startups = safe_load_json(resolve(cfg["files"]["startups"]), {"data": []}).get("data", [])
    startup = startups[idx] if 0 <= idx < len(startups) else {}
    rendered = render_prompt(template_text, startup, cfg["profile"].get("signature", ""))
    return jsonify({"rendered": rendered, "company": startup.get("EntrepriseName", "—")})


@app.route("/startups")
def startups_page():
    cfg = load_config()
    data = safe_load_json(resolve(cfg["files"]["startups"]), {"data": []})
    items = data.get("data", []) if isinstance(data, dict) else []
    return render_template("startups.html", startups=items)


@app.route("/api/startups", methods=["PUT"])
def api_startups_replace():
    """Overwrite the full startups list (simplest path for an editable table)."""
    cfg = load_config()
    payload = request.get_json(silent=True) or {}
    items = payload.get("data", [])
    if not isinstance(items, list):
        return jsonify({"error": "data must be a list"}), 400
    save_json(resolve(cfg["files"]["startups"]), {"data": items})
    return jsonify({"ok": True, "count": len(items)})


@app.route("/api/startups/delete", methods=["POST"])
def api_startups_delete():
    """Delete one startup from startups.json.

    Identifies the row by email (case-insensitive) if provided, else by name.
    Returns 404 if no match. Only removes the FIRST match — duplicates are
    left in place so the user can retry.
    """
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    name = (payload.get("name") or "").strip().lower()

    if not email and not name:
        return jsonify({"ok": False, "error": "email ou name requis"}), 400

    cfg = load_config()
    path = resolve(cfg["files"]["startups"])
    data = safe_load_json(path, {"data": []})
    items = data.get("data", []) if isinstance(data, dict) else data

    for i, s in enumerate(items):
        s_email = (s.get("EntrepriseContactEmail") or "").strip().lower()
        s_name = (s.get("EntrepriseName") or "").strip().lower()
        match = False
        if email and s_email == email:
            match = True
        elif not email and name and s_name == name:
            match = True
        if match:
            removed = items.pop(i)
            save_json(path, {"data": items})
            return jsonify({
                "ok": True,
                "removed": removed.get("EntrepriseName") or removed.get("EntrepriseContactEmail") or "",
                "remaining": len(items),
            })

    return jsonify({"ok": False, "error": "Startup introuvable dans le fichier."}), 404


@app.route("/api/startups/import", methods=["POST"])
def api_startups_import():
    """Parse an uploaded CSV/JSON file and return the extracted rows WITHOUT
    saving them. The client injects them at the top of the table as pending;
    the user validates (edits / deletes individual rows if needed) and clicks
    "Enregistrer" to persist via the existing PUT /api/startups endpoint.

    Required field: EntrepriseContactEmail. Name + contact are derived from
    the email itself (domain / local-part). Other fields stay empty.
    Duplicates (by email) against the already-saved file are filtered out.
    """
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Aucun fichier fourni."}), 400

    content = f.read()
    if not content:
        return jsonify({"ok": False, "error": "Fichier vide."}), 400

    try:
        raw_rows, headers = parse_startups_file(f.filename, content)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Erreur de lecture : {type(e).__name__}: {e}"}), 400

    mapping = detect_mapping(headers)
    if "EntrepriseContactEmail" not in mapping.values():
        return jsonify({
            "ok": False,
            "error": ("Colonne email manquante. L'email est obligatoire. "
                      "Entêtes détectées : " + ", ".join(headers or ["(aucune)"])),
        }), 400

    mapped_rows = [map_row(r, mapping) for r in raw_rows if isinstance(r, dict)]
    extract_from_email(mapped_rows)

    # Dedup against what's already persisted on disk
    cfg = load_config()
    startups_path = resolve(cfg["files"]["startups"])
    existing = safe_load_json(startups_path, {"data": []})
    existing_items = existing.get("data", []) if isinstance(existing, dict) else existing
    existing_emails = {
        (s.get("EntrepriseContactEmail") or "").strip().lower()
        for s in existing_items
        if s.get("EntrepriseContactEmail")
    }

    new_rows = []
    skipped_invalid = 0
    skipped_duplicates = 0
    seen_in_batch = set()
    for r in mapped_rows:
        email = (r.get("EntrepriseContactEmail") or "").strip()
        if not email or "@" not in email:
            skipped_invalid += 1
            continue
        low = email.lower()
        if low in existing_emails or low in seen_in_batch:
            skipped_duplicates += 1
            continue
        seen_in_batch.add(low)
        new_rows.append(r)

    return jsonify({
        "ok": True,
        "rows": new_rows,
        "accepted": len(new_rows),
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
        "total_seen": len(mapped_rows),
    })


@app.errorhandler(413)
def handle_too_large(_e):
    return jsonify({"ok": False, "error": "Fichier trop volumineux (max 5 Mo)."}), 413


@app.route("/emails")
def emails_page():
    cfg = load_config()
    emails = safe_load_json(resolve(cfg["files"]["generated_emails"]), [])
    tracking = safe_load_json(resolve(cfg["files"]["tracking"]), {})
    sent = set(tracking.get("sent_emails", []))
    replies = tracking.get("replies", {})

    status_counts = {s: 0 for s in STATUS_ORDER}
    for i, e in enumerate(emails):
        company = e.get("company_name")
        e["_sent"] = company in sent
        e["_reply"] = replies.get(company)
        status, is_manual = resolve_status(company, tracking)
        e["_status"] = status
        e["_status_manual"] = is_manual
        # Position in the *file*, captured before the sort below. The API
        # routes address emails by their index in generated_emails.json, so
        # the template must emit this — not the post-sort loop index.
        e["_index"] = i
        status_counts[status] += 1

    # Drafts on top, then everything else. Stable sort preserves file order
    # inside each group (so the most recently generated draft stays first).
    status_priority = {s: i for i, s in enumerate(STATUS_ORDER)}
    emails.sort(key=lambda e: status_priority.get(e["_status"], 99))

    return render_template(
        "emails.html",
        emails=emails,
        status_order=STATUS_ORDER,
        status_labels=STATUS_LABELS,
        status_counts=status_counts,
    )


@app.route("/api/emails/<int:index>", methods=["PUT"])
def api_emails_update(index):
    cfg = load_config()
    path = resolve(cfg["files"]["generated_emails"])
    emails = safe_load_json(path, [])
    if not 0 <= index < len(emails):
        return jsonify({"error": "index out of range"}), 404
    payload = request.get_json(silent=True) or {}
    for field in ("email_subject", "email_body", "hr_name", "hr_email"):
        if field in payload:
            emails[index][field] = payload[field]
    save_json(path, emails)
    return jsonify({"ok": True})


@app.route("/api/emails/<int:index>/test-self", methods=["POST"])
def api_emails_test_self(index):
    """Send the email to the configured sender (self) instead of the HR contact.

    Does NOT update tracking. Used to preview the real rendered email in
    your inbox before dispatching to the actual recipient.
    """
    cfg = load_config()
    path = resolve(cfg["files"]["generated_emails"])
    emails = safe_load_json(path, [])
    if not 0 <= index < len(emails):
        return jsonify({"ok": False, "error": "Email introuvable."}), 404

    smtp = cfg["smtp"]
    if not smtp.get("user") or not smtp.get("password"):
        return jsonify({"ok": False, "error": "Identifiants SMTP manquants."}), 400

    email_data = emails[index]
    profile = cfg["profile"]
    sender_name = profile.get("sender_display_name") or smtp["user"]

    msg = build_message(
        sender_email=smtp["user"],
        sender_name=sender_name,
        recipient_name="Test (moi)",
        recipient_email=smtp["user"],
        subject=f"[TEST] {email_data.get('email_subject', '')}",
        body=email_data.get("email_body", ""),
        resume_link=profile.get("resume_link", ""),
    )

    ok, err = send_one(smtp, msg, smtp["user"])
    if ok:
        return jsonify({
            "ok": True,
            "message": f"Email envoyé à {smtp['user']} (sujet préfixé [TEST]).",
        })
    return jsonify({"ok": False, "error": err}), 200


@app.route("/api/emails/<int:index>", methods=["DELETE"])
def api_emails_delete(index):
    cfg = load_config()
    path = resolve(cfg["files"]["generated_emails"])
    emails = safe_load_json(path, [])
    if not 0 <= index < len(emails):
        return jsonify({"error": "index out of range"}), 404
    removed = emails.pop(index)
    save_json(path, emails)
    return jsonify({"ok": True, "removed": removed.get("company_name")})


# --------------------------------------------------------------------------- #
# Jobs: generate / send / stream
# --------------------------------------------------------------------------- #

@app.route("/api/generate", methods=["POST"])
def api_generate():
    cfg = load_config()
    if not cfg["openai"].get("api_key"):
        return jsonify({"error": "OpenAI API key missing. Set it in Configuration."}), 400

    payload = request.get_json(silent=True) or {}
    template_id = payload.get("template_id")
    try:
        limit = int(payload.get("limit") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "limit doit être un nombre."}), 400
    if limit < 0:
        return jsonify({"error": "limit doit être positif."}), 400

    def target(on_progress, should_stop):
        return generate_all(
            cfg,
            on_progress=on_progress,
            should_stop=should_stop,
            template_id=template_id,
            limit=limit,
        )

    try:
        job_id = job_manager.start(target, "generate")
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"job_id": job_id})


@app.route("/api/send", methods=["POST"])
def api_send():
    cfg = load_config()
    if not cfg["smtp"].get("user") or not cfg["smtp"].get("password"):
        return jsonify({"error": "SMTP credentials missing. Set them in Configuration."}), 400

    payload = request.get_json(silent=True) or {}
    only = payload.get("only")
    if only is not None and not isinstance(only, list):
        return jsonify({"error": "'only' must be a list of company names."}), 400

    def target(on_progress, should_stop):
        return send_all(cfg, on_progress=on_progress, only=only, should_stop=should_stop)

    try:
        job_id = job_manager.start(target, "send")
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"job_id": job_id})


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def api_job_cancel(job_id):
    if job_manager.cancel(job_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Job not running or not found."}), 404


@app.route("/api/send-followups", methods=["POST"])
def api_send_followups():
    cfg = load_config()
    if not cfg["smtp"].get("user") or not cfg["smtp"].get("password"):
        return jsonify({"error": "Identifiants SMTP manquants."}), 400
    if not cfg["openai"].get("api_key"):
        return jsonify({"error": "Clé OpenAI manquante."}), 400

    def target(on_progress, should_stop):
        return send_followups(cfg, on_progress=on_progress, should_stop=should_stop)

    try:
        job_id = job_manager.start(target, "followups")
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"job_id": job_id})


@app.route("/api/check-replies", methods=["POST"])
def api_check_replies():
    cfg = load_config()
    if not cfg["smtp"].get("user") or not cfg["smtp"].get("password"):
        return jsonify({"error": "Identifiants email manquants (section SMTP)."}), 400

    def target(on_progress, should_stop):
        return check_replies(cfg, on_progress=on_progress, should_stop=should_stop)

    try:
        job_id = job_manager.start(target, "check-replies")
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"job_id": job_id})


@app.route("/api/status/<path:company>", methods=["PUT", "DELETE"])
def api_set_status(company):
    """PUT sets a manual status for a company. DELETE clears the override so
    the status falls back to the auto-derived value."""
    cfg = load_config()
    path = resolve(cfg["files"]["tracking"])
    tracking = safe_load_json(path, {})
    tracking.setdefault("statuses", {})

    if request.method == "DELETE":
        tracking["statuses"].pop(company, None)
        save_json(path, tracking)
        status, is_manual = resolve_status(company, tracking)
        return jsonify({"ok": True, "status": status, "manual": is_manual})

    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status")
    if new_status not in STATUS_LABELS:
        return jsonify({"ok": False, "error": f"Statut inconnu : {new_status}"}), 400
    tracking["statuses"][company] = new_status
    save_json(path, tracking)
    return jsonify({"ok": True, "status": new_status, "manual": True})


@app.route("/api/replies/<path:company>", methods=["DELETE"])
def api_replies_remove(company):
    """Drop a stored reply so the next check can re-detect it (debugging aid)."""
    cfg = load_config()
    path = resolve(cfg["files"]["tracking"])
    tracking = safe_load_json(path, {})
    tracking.setdefault("replies", {})
    if company in tracking["replies"]:
        del tracking["replies"][company]
        save_json(path, tracking)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Réponse introuvable"}), 404


@app.route("/api/jobs/current")
def api_job_current():
    job = job_manager.current()
    if not job:
        return jsonify({"job": None})
    return jsonify({
        "id": job["id"],
        "label": job["label"],
        "status": job["status"],
        "started_at": job["started_at"],
        "ended_at": job["ended_at"],
        "events": job["events"][-300:],
        "result": job["result"],
        "error": job["error"],
    })


@app.route("/api/jobs/<job_id>/stream")
def api_job_stream(job_id):
    q = job_manager.subscribe(job_id)
    if q is None:
        return jsonify({"error": "job not found"}), 404

    def gen():
        while True:
            try:
                event = q.get(timeout=20)
            except Empty:
                yield ": keepalive\n\n"
                continue
            if event is None:
                yield "event: end\ndata: {}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"

    return Response(gen(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# --------------------------------------------------------------------------- #
# Maintenance
# --------------------------------------------------------------------------- #

@app.route("/api/tracking/reset", methods=["POST"])
def api_tracking_reset():
    """Reset tracking entries.

    Payload:
        scope: "sent" | "processed" | "all" (default "sent")
        companies: optional list of company names. When provided, only these
            entries are removed from the target list(s). When omitted, the
            entire list is cleared (backwards-compatible nuclear reset).
    """
    cfg = load_config()
    payload = request.get_json(silent=True) or {}
    scope = payload.get("scope", "sent")
    companies = payload.get("companies")

    path = resolve(cfg["files"]["tracking"])
    tracking = safe_load_json(path, {})
    tracking.setdefault("sent_emails", [])
    tracking.setdefault("processed_companies", [])

    removed = {"sent": 0, "processed": 0}

    if companies is not None:
        if not isinstance(companies, list):
            return jsonify({"error": "'companies' must be a list"}), 400
        target = set(companies)
        if scope in ("sent", "all"):
            before = len(tracking["sent_emails"])
            tracking["sent_emails"] = [c for c in tracking["sent_emails"] if c not in target]
            removed["sent"] = before - len(tracking["sent_emails"])
        if scope in ("processed", "all"):
            before = len(tracking["processed_companies"])
            tracking["processed_companies"] = [c for c in tracking["processed_companies"] if c not in target]
            removed["processed"] = before - len(tracking["processed_companies"])
    else:
        if scope in ("sent", "all"):
            removed["sent"] = len(tracking["sent_emails"])
            tracking["sent_emails"] = []
        if scope in ("processed", "all"):
            removed["processed"] = len(tracking["processed_companies"])
            tracking["processed_companies"] = []

    save_json(path, tracking)
    return jsonify({"ok": True, "scope": scope, "removed": removed})


@app.route("/api/emails/clear", methods=["POST"])
def api_emails_clear():
    cfg = load_config()
    save_json(resolve(cfg["files"]["generated_emails"]), [])
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# Credential tests — validate without saving
# --------------------------------------------------------------------------- #

@app.route("/api/test/openai", methods=["POST"])
def api_test_openai():
    """Verify the OpenAI key + model by issuing a tiny completion.

    Uses values from the POST body if present (so users can test unsaved
    form values), falling back to config.json.
    """
    from openai import OpenAI, AuthenticationError, NotFoundError, APIError

    payload = request.get_json(silent=True) or {}
    cfg = load_config()
    api_key = (payload.get("api_key") or cfg["openai"]["api_key"]).strip()
    model = (payload.get("model") or cfg["openai"]["model"]).strip()

    if not api_key:
        return jsonify({"ok": False, "error": "Clé API manquante."}), 400

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
        )
        return jsonify({
            "ok": True,
            "model": resp.model,
            "message": f"OK — modèle '{resp.model}' répond.",
        })
    except AuthenticationError:
        return jsonify({"ok": False, "error": "Clé API invalide (401)."}), 200
    except NotFoundError:
        return jsonify({"ok": False, "error": f"Modèle '{model}' introuvable."}), 200
    except APIError as e:
        return jsonify({"ok": False, "error": f"OpenAI API error: {e}"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 200


@app.route("/api/test/smtp", methods=["POST"])
def api_test_smtp():
    """Connect + login to the SMTP server without sending any email."""
    import smtplib
    import ssl

    payload = request.get_json(silent=True) or {}
    cfg = load_config()
    user = (payload.get("user") or cfg["smtp"]["user"]).strip()
    password = payload.get("password") or cfg["smtp"]["password"]
    server = (payload.get("server") or cfg["smtp"]["server"]).strip()
    port = int(payload.get("port") or cfg["smtp"]["port"])

    if not user or not password:
        return jsonify({"ok": False, "error": "Identifiants SMTP manquants."}), 400

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(server, port, context=context, timeout=10) as s:
            s.login(user, password)
        return jsonify({"ok": True, "message": f"OK — connecté à {server}:{port} en tant que {user}."})
    except smtplib.SMTPAuthenticationError:
        return jsonify({"ok": False, "error": "Identifiants refusés (vérifiez le mot de passe d'application)."}), 200
    except smtplib.SMTPException as e:
        return jsonify({"ok": False, "error": f"Erreur SMTP : {e}"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 200


if __name__ == "__main__":
    import os
    drift = detect_env_drift(load_config())
    if drift:
        print("[WARN] .env and config.json have diverged — config.json is the source of truth:")
        for msg in drift:
            print(f"  - {msg}")
    port = int(os.environ.get("PORT", 8000))
    app.run(debug=True, port=port, threaded=True)
