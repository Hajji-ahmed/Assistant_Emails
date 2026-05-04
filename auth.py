"""Session-based authentication backed by users.json.

Single-user local app — no registration, no password reset UI. Add users by
editing users.json (passwords must be hashed with werkzeug.security).
"""
import json
from functools import wraps
from pathlib import Path
from flask import session, redirect, url_for, request, jsonify
from werkzeug.security import check_password_hash

USERS_FILE = Path(__file__).parent / "users.json"


def load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def authenticate(email: str, password: str) -> dict | None:
    users = load_users()
    user = users.get(email.strip().lower()) or users.get(email)
    if not user:
        return None
    if check_password_hash(user["password_hash"], password):
        return user
    return None


def current_user() -> dict | None:
    email = session.get("user_email")
    if not email:
        return None
    return load_users().get(email)


def login_required(view):
    """Protect a route. JSON-accepting requests get 401, others redirect."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_email"):
            wants_json = (
                request.is_json
                or request.accept_mimetypes.best == "application/json"
                or request.path.startswith("/api/")
            )
            if wants_json:
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped
