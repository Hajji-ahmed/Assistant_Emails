"""Generate personalized emails using OpenAI.

Two entry points:
- CLI: `python generate_emails.py` (loads config from config.json)
- Programmatic: `generate_all(config, on_progress=callback)` for Flask routes
"""
import json
import os
from pathlib import Path
from openai import OpenAI

from config import load_config
from templates_mgr import ensure_prompts_layout, load_body, get_meta

BASE_DIR = Path(__file__).parent


def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {path}: {str(e)}")
        return default


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_prompt_template(template_path):
    path = Path(template_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def render_prompt(template, startup, signature):
    """Replace {VarName} placeholders with values from the startup record.

    Supported vars: every key on the startup dict + {Signature}.
    Missing keys fall back to empty string.
    """
    context = {**startup, "Signature": signature}
    try:
        return template.format_map(_SafeDict(context))
    except Exception as e:
        print(f"Error rendering prompt: {e}")
        return template


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def parse_email_response(email_text):
    parts = email_text.split('\n\n', 1)
    if len(parts) >= 2:
        subject_line = parts[0].strip()
        subject = subject_line[8:].strip() if subject_line.startswith('Subject:') else subject_line
        body = parts[1].strip()
    else:
        subject = "Internship Request"
        body = email_text.strip()
    return subject, body


def generate_single(client, model, temperature, max_tokens, prompt):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    email_text = (response.choices[0].message.content or '').strip()
    return parse_email_response(email_text)


def generate_all(config, on_progress=None, should_stop=None, template_id=None, limit=None):
    """Generate emails for every startup that hasn't been processed yet.

    Args:
        config: dict from load_config()
        on_progress: optional callable(event: dict) for streaming progress.
            Event types: "info", "success", "skip", "error", "quota", "done", "cancelled".
        should_stop: optional callable() -> bool — returning True aborts at the
            next iteration (checked before each startup).
        template_id: optional template id to use. Defaults to
            config["prompts"]["active"] (the selected campaign template).
        limit: optional int — stop after generating this many new emails.
            None or 0 means generate for all eligible startups.
    Returns:
        dict with counts: {"generated": int, "skipped": int, "errors": int, "total": int}
    """
    def emit(event_type, message, **extra):
        if on_progress:
            on_progress({"type": event_type, "message": message, **extra})
        else:
            print(f"[{event_type.upper()}] {message}")

    api_key = config["openai"]["api_key"]
    if not api_key:
        raise ValueError("Missing OpenAI API key in config.")

    files = config["files"]
    startups_path = BASE_DIR / files["startups"]
    emails_path = BASE_DIR / files["generated_emails"]
    tracking_path = BASE_DIR / files["tracking"]

    startups = load_json(startups_path, {"data": []}).get("data", [])
    if not startups:
        emit("error", "No startup data loaded.")
        return {"generated": 0, "skipped": 0, "errors": 0, "total": 0}

    existing_emails = load_json(emails_path, [])
    tracking = load_json(tracking_path, {"processed_companies": []})
    tracking.setdefault("processed_companies", [])

    processed = {e["company_name"] for e in existing_emails} | set(tracking["processed_companies"])

    # Resolve template: explicit template_id > config.prompts.active > legacy file
    tpl_id = template_id or config.get("prompts", {}).get("active")
    meta = get_meta(config, tpl_id) if tpl_id else None
    if meta:
        template = load_body(config, tpl_id)
        template_label = meta["name"]
    else:
        # Fallback: legacy prompt_template.txt (pre-gallery)
        template = load_prompt_template(files["prompt_template"])
        tpl_id = "legacy"
        template_label = "legacy"
    emit("info", f"Template utilisé : {template_label}")
    signature = config["profile"].get("signature", "")

    client = OpenAI(api_key=api_key)
    model = config["openai"]["model"]
    temperature = float(config["openai"].get("temperature", 0.2))
    max_tokens = int(config["openai"].get("max_tokens", 500))

    counts = {"generated": 0, "skipped": 0, "errors": 0, "total": len(startups)}

    # Normalize limit: None or 0 means "no limit"
    limit = int(limit) if limit else 0
    if limit > 0:
        emit("info", f"Limite définie : {limit} email(s) maximum.")

    for s in startups:
        if should_stop and should_stop():
            emit("cancelled", "Génération annulée par l'utilisateur.")
            break

        if limit > 0 and counts["generated"] >= limit:
            emit("info", f"Limite de {limit} atteinte. Arrêt de la génération.")
            break

        company_name = s.get('EntrepriseName', 'Unknown Company')

        if company_name in processed:
            emit("skip", f"{company_name} - already processed.")
            counts["skipped"] += 1
            continue

        try:
            emit("info", f"Generating email for {company_name}...")
            prompt = render_prompt(template, s, signature)
            subject, body = generate_single(client, model, temperature, max_tokens, prompt)

            email_obj = {
                "company_name": company_name,
                "company_location": s.get('EntrepriseVille', ''),
                "company_technology": s.get('EntrepriseTechnologie', ''),
                "company_sector": s.get('EntrepriseSecteurActivite', ''),
                "hr_name": s.get('EntrepriseContactName', ''),
                "hr_email": s.get('EntrepriseContactEmail', ''),
                "email_subject": subject,
                "email_body": body,
                "template_id": tpl_id,
            }
            # Prepend so the newest draft always shows first on /emails
            existing_emails.insert(0, email_obj)
            save_json(emails_path, existing_emails)

            tracking["processed_companies"].append(company_name)
            save_json(tracking_path, tracking)

            counts["generated"] += 1
            emit("success", f"Email saved for {company_name}", company=company_name)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "quota" in error_str.lower():
                emit("quota", f"API quota reached. Processed {counts['generated']} so far.")
                counts["errors"] += 1
                break
            counts["errors"] += 1
            emit("error", f"Failed for {company_name}: {error_str}", company=company_name)

    emit("done", f"Generation complete. Generated: {counts['generated']}, Skipped: {counts['skipped']}, Errors: {counts['errors']}")
    return counts


def main():
    config = load_config()
    generate_all(config)


if __name__ == "__main__":
    main()
