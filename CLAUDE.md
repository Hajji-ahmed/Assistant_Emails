# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project summary

Personal Flask app to manage an internship/cold-email campaign: bulk-generate personalized emails with OpenAI, send via Gmail SMTP, detect replies via IMAP, and track each prospect through a 7-status CRM pipeline. JSON files on disk are the only persistence layer — there is no database, no test suite, no build step, and the app is intended for single-user local use.

See `README.md` for the full feature list and end-user workflow; this file focuses on the architectural facts that span multiple files.

## Commands

The project uses a `.venv` at the repo root and PowerShell on Windows.

```powershell
# Activate venv (one-time per shell)
.\.venv\Scripts\Activate.ps1

# Install / refresh deps
pip install -r requirements.txt

# Run the Flask app (default port 8000)
python app.py

# Override port if 8000 is reserved by Hyper-V/WSL
$env:PORT = "5555"; python app.py
```

CLI fallbacks bypass the UI and the JobManager — useful for scripted runs or debugging a single stage:

```powershell
python generate_emails.py    # generate drafts with the active campaign template
python send_emails.py        # send everything in generated_emails.json not in tracking.sent_emails
python check_replies.py      # scan IMAP for replies to already-sent emails
python send_followups.py     # send follow-ups for emails older than followups.delay_days
```

There is **no test suite, no linter config, and no build step.** Do not invent commands for those — say so explicitly when asked.

## Architecture

### Request flow

`app.py` is the single Flask entrypoint. HTML routes render Jinja templates from `templates/`; mutating routes return JSON `{ok: bool, ...}`. Long-running actions (generate, send, follow-ups, IMAP check) are dispatched to `JobManager` and surfaced to the UI via SSE.

### JobManager — single-slot, cooperative cancel (`jobs.py`)

Only **one** job can run at a time (`start()` raises `RuntimeError` if another is running → app.py returns 409). The target function must accept `(on_progress, should_stop)`:
- `on_progress(event)` — buffered on the job and fanned out to live SSE subscribers. New subscribers replay all buffered events before joining the live stream.
- `should_stop()` — checked at every safe checkpoint inside long loops; cancel propagates via `cancel_event.set()`. Use `send_emails._sleep_cancellable` for any rate-limited sleep you add so the user can cancel mid-batch.

This is why all batch loops (`generate_all`, `send_all`, `send_followups`, `check_replies`) are written as iterables that check `should_stop` per item and call `emit(...)` rather than `print`.

### Config: `config.json` is the source of truth (`config.py`)

`.env` is **only** read on first launch to bootstrap `config.json`. After that, editing `.env` has no effect — `detect_env_drift()` warns the user on `/config` if the two diverge. `load_config()` deep-merges stored values onto `DEFAULTS`, so adding a new field to `DEFAULTS` is forward-compatible without a migration.

### Persistence model — two split JSON files

State lives in two files (paths come from `config.files`):

- `generated_emails.json` — a flat list of email drafts (`{company_name, hr_email, email_subject, email_body, template_id, ...}`). New drafts are **prepended** so the freshest show at the top of `/emails`.
- `email_tracking.json` — runtime state with these keys: `processed_companies` (gen dedup), `sent_emails`, `sent_dates`, `daily_counters[YYYY-MM-DD]`, `replies[company]`, `followups_sent[company]`, `statuses[company]` (manual override).

**Status resolution** (`app.py:resolve_status`) falls through: manual override in `statuses` → `replied` if in `replies` → `sent` if in `sent_emails` → default `draft`. Manual overrides win — never write to `replies`/`sent_emails` to fake a status change; write to `statuses`.

Dedup at generation time uses **both** `processed_companies` AND every `company_name` already in `generated_emails.json` (see `generate_emails.py:122`). When picking "next companies" to operate on, mirror this — skipping only by tracking will re-process drafts that were manually generated.

### Prompt-template gallery (`templates_mgr.py`)

Templates are plain `.txt` files in `prompts/`. Metadata lives in `config.prompts.list[]` with `kind: "campaign" | "followup"` and two pointers — `active` (used by Generate) and `active_followup` (used by follow-ups). `ensure_prompts_layout()` is idempotent and runs on app import to seed `default` + `followup` from the legacy `prompt_template.txt` if missing.

Templates use `{VarName}` placeholders. `render_prompt()` substitutes every key on the startup dict plus `{Signature}`; missing keys resolve to `""` via a `_SafeDict` (so a template never crashes on a sparse row). Generation uses subject/body parsing in `parse_email_response` — the LLM is expected to return `Subject: ...\n\n<body>`.

### IMAP reply detection (`check_replies.py`)

Matches replies by **domain** of the recipient (not exact address) for non-free domains, so `marie@acme.ma` counts as a reply to `contact@acme.ma`. Free-mail domains (gmail/yahoo/outlook/...) fall back to exact-address match to avoid over-matching. Walks results newest-first, filters out `noreply`/`postmaster`/`mailer-daemon`/the user's own address, then records the first match.

Selects `[Gmail]/All Mail` (or its French variant) before falling back to `INBOX` — needed because archived replies wouldn't appear in INBOX.

### Auth (`auth.py`)

Session-based, single-user, backed by `users.json` with werkzeug-hashed passwords. There is no registration UI — users are added by editing `users.json`. Login template at `templates/login.html`.

## Conventions and gotchas

- **Encoding**: always read/write JSON with `encoding='utf-8'` and `ensure_ascii=False`. The PowerShell console renders many UTF-8 chars as `�` (cp1252 limitation) — when verifying file contents, re-`Read` the file rather than trusting console output.
- **Source-of-truth files are gitignored** (`config.json`, `.env`, `startups.json`, `resume.json`, `generated_emails.json`, `email_tracking.json`, `users.json`). Never commit them or write real secrets into examples.
- **`send_all` aborts the whole batch on permanent failure** after `max_retries=3` attempts (`send_emails.py:194-197`) — this is intentional (SMTP auth failure usually means the credentials are wrong and retrying every email wastes time). Don't change to "skip-and-continue" without thinking about that.
- **Daily cap**: `sending.daily_limit` (0 = unlimited) is enforced against `tracking.daily_counters[today]`. Both `send_all` and `send_followups` respect it and share the same counter.
- **Cancellable sleep**: replace any `time.sleep(n)` in a long loop with `_sleep_cancellable(n, should_stop)` so cancel doesn't have to wait out the delay.
- **Startups dedup**: `startups_import.merge_at_top` and the `/api/startups/import` endpoint key on **email** (case-insensitive), not company name. `extract_from_email` only fills `EntrepriseName`/`EntrepriseContactName` deterministically from the address and **never overwrites** an existing value.
