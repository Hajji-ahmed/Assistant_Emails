"""Persistent configuration for the Flask app.

Single source of truth: config.json at project root.
On first launch (no config.json), values are bootstrapped from .env so
existing users don't lose their settings. After that, .env is ignored —
edit values via the /config UI (which writes to config.json).
"""
import json
from pathlib import Path
from dotenv import dotenv_values

CONFIG_FILE = Path(__file__).parent / "config.json"
ENV_FILE = Path(__file__).parent / ".env"

DEFAULTS = {
    "openai": {
        "api_key": "",
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "max_tokens": 500,
    },
    "smtp": {
        "user": "",
        "password": "",
        "server": "smtp.gmail.com",
        "port": 465,
        "sender_name": "",
    },
    "profile": {
        "resume_link": "https://drive.google.com/drive/u/0/folders/1Yqsp9SNECKTkWmav0iG0b70HcQ5FGwzW",
        "phone": "+212 603251761",
        "linkedin": "",
        "github": "",
        "signature": "Cordialement,\nAhmed Hajji\n+212 603251761 | ahmed.hajji.23@ump.ac.ma",
        "sender_display_name": "Hajji Ahmed",
    },
    "sending": {
        "send_delay_seconds": 2,
        "daily_limit": 100,
    },
    "imap": {
        "server": "imap.gmail.com",
        "port": 993,
        "lookback_days": 60,
    },
    "followups": {
        "delay_days": 7,
    },
    "files": {
        "startups": "startups.json",
        "resume": "resume.json",
        "generated_emails": "generated_emails.json",
        "tracking": "email_tracking.json",
        "prompt_template": "prompt_template.txt",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively; override wins on leaves."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _bootstrap_from_env() -> dict:
    """Build initial config from .env values when config.json doesn't exist yet."""
    if not ENV_FILE.exists():
        return dict(DEFAULTS)

    env = dotenv_values(ENV_FILE)
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy

    if env.get("OPENAI_API_KEY"):
        cfg["openai"]["api_key"] = env["OPENAI_API_KEY"]
    if env.get("OPENAI_MODEL"):
        cfg["openai"]["model"] = env["OPENAI_MODEL"]
    if env.get("TEMPERATURE"):
        try:
            cfg["openai"]["temperature"] = float(env["TEMPERATURE"])
        except ValueError:
            pass
    if env.get("MAX_OUTPUT_TOKENS"):
        try:
            cfg["openai"]["max_tokens"] = int(env["MAX_OUTPUT_TOKENS"])
        except ValueError:
            pass
    if env.get("GMAIL_USER"):
        cfg["smtp"]["user"] = env["GMAIL_USER"]
    if env.get("GMAIL_APP_PASSWORD"):
        cfg["smtp"]["password"] = env["GMAIL_APP_PASSWORD"]

    return cfg


def load_config() -> dict:
    """Load config.json, or bootstrap it from .env on first run.

    Missing keys are filled from DEFAULTS so the schema stays stable when
    new fields are added later.
    """
    if not CONFIG_FILE.exists():
        cfg = _bootstrap_from_env()
        save_config(cfg)
        return cfg

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        stored = json.load(f)
    return _deep_merge(DEFAULTS, stored)


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def detect_env_drift(cfg: dict) -> list[str]:
    """Return a list of messages if .env still holds values that differ
    from config.json. .env is only used for first-run bootstrap, so any
    divergence is usually stale config the user forgot to clean up."""
    if not ENV_FILE.exists():
        return []
    env = dotenv_values(ENV_FILE)
    warnings = []
    pairs = [
        ("OPENAI_API_KEY", cfg["openai"]["api_key"], "openai.api_key"),
        ("GMAIL_USER", cfg["smtp"]["user"], "smtp.user"),
        ("GMAIL_APP_PASSWORD", cfg["smtp"]["password"], "smtp.password"),
    ]
    for env_key, cfg_value, cfg_path in pairs:
        env_value = env.get(env_key)
        if env_value and env_value != cfg_value:
            warnings.append(f".env {env_key} differs from config.json {cfg_path}")
    return warnings
