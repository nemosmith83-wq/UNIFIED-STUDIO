"""Multi-user authentication for Unified Studio.

Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes. Browser sessions
use opaque, HttpOnly cookies stored in a separate SQLite database.
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Optional, Dict

DB_PATH = Path(os.getenv("UNIFIED_AUTH_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "auth.db")))
COOKIE_NAME = "unified_studio_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
_lock = Lock()
_attempts = {}

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _lock, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                last_seen INTEGER NOT NULL
            )
        """)
        conn.commit()

def registration_available():
    init_db()
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return True

def _hash_password(password: str, salt_hex: str = ""):
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return salt.hex(), digest.hex()

def _valid_password(password: str):
    return isinstance(password, str) and 10 <= len(password) <= 200 and any(c.isalpha() for c in password) and any(c.isdigit() for c in password)

def _rate_key(client_id: str):
    now = int(time.time())
    item = _attempts.get(client_id)
    if not item or now - item[0] > 600:
        _attempts[client_id] = [now, 0]
        return True
    return item[1] < 8

def record_failure(client_id: str):
    now = int(time.time())
    item = _attempts.setdefault(client_id, [now, 0])
    item[1] += 1

def clear_failures(client_id: str):
    _attempts.pop(client_id, None)

def create_user(username: str, display_name: str, password: str):
    init_db()
    username = username.strip().lower()
    display_name = display_name.strip() or username
    if not re_username(username):
        raise ValueError("Username must be 3-32 characters using letters, numbers, dot, dash, or underscore.")
    if not _valid_password(password):
        raise ValueError("Password must be 10-200 characters and contain at least one letter and one number.")
    user_id = secrets.token_hex(16)
    salt, digest = _hash_password(password)
    try:
        with _lock, _connect() as conn:
            conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (user_id, username, display_name[:80], digest, salt, int(time.time())))
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("That username is already registered.")
    return {"id": user_id, "username": username, "display_name": display_name[:80]}

def re_username(value):
    import re
    return bool(re.fullmatch(r"[a-zA-Z0-9._-]{3,32}", value))

def verify_user(username: str, password: str):
    init_db()
    username = username.strip().lower()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return None
    salt, digest = _hash_password(password, row["password_salt"])
    if not hmac.compare_digest(digest, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}

def create_session(user_id: str):
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(time.time())
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)", (token_hash, user_id, now, now + SESSION_TTL_SECONDS, now))
        conn.commit()
    return token

def get_user_by_session(token: Optional[str]):
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(time.time())
    with _connect() as conn:
        row = conn.execute("""
            SELECT u.id, u.username, u.display_name
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?
        """, (token_hash, now)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE sessions SET last_seen = ? WHERE token_hash = ?", (now, token_hash))
        conn.commit()
    return dict(row)

def delete_session(token: Optional[str]):
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()
