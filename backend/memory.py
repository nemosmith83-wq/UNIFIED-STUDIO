"""
memory.py — Unified persistent memory layer (SQLite).
Optimized for 8GB RAM systems with connection pooling.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from threading import Lock

DB_PATH = os.environ.get("UNIFIED_DB_PATH", "data/unified.db")
_db_lock = Lock()
_connection_pool = None


def init_db() -> None:
    """Initialize database with all required tables."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Conversations table
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            role        TEXT    NOT NULL CHECK(role IN ('user','assistant','system')),
            content     TEXT    NOT NULL,
            agent       TEXT    DEFAULT 'general',
            timestamp   TEXT    DEFAULT (datetime('now'))
        )
    """)

    # Memories table
    c.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT    UNIQUE NOT NULL,
            value       TEXT    NOT NULL,
            updated_at  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # Generated images metadata
    c.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            filename    TEXT    NOT NULL,
            prompt      TEXT,
            engine      TEXT,
            timestamp   TEXT    DEFAULT (datetime('now'))
        )
    """)

    # Index for fast lookups
    c.execute("CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations (session_id, id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_images_session ON images (session_id)")

    conn.commit()
    conn.close()


def get_db() -> sqlite3.Connection:
    """Get a thread-safe database connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Use WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def save_message(session_id: str, role: str, content: str, agent: str = "general") -> None:
    """Save a message to conversation history."""
    with _db_lock:
        conn = get_db()
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, agent) VALUES (?, ?, ?, ?)",
            (session_id, role, content[:8000], agent)
        )
        conn.commit()
        conn.close()


def get_history(session_id: str, limit: int = 20) -> List[Dict]:
    """Get recent conversation history for a session."""
    with _db_lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT role, content, agent, timestamp FROM conversations "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ? ",
            (session_id, limit)
        ).fetchall()
        conn.close()
    
    return [dict(r) for r in reversed(rows)]


def clear_history(session_id: str) -> int:
    """Delete all messages for a session and return the number deleted."""
    with _db_lock:
        conn = get_db()
        cur = conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.commit()
        count = cur.rowcount
        conn.close()
    return count


def search_history(session_id: str, query: str, limit: int = 20) -> List[Dict]:
    """Search messages in one session."""
    with _db_lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT role, content, agent, timestamp FROM conversations "
            "WHERE session_id = ? AND content LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, f"%{query}%", limit)
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def list_sessions() -> List[Dict]:
    """List conversation sessions with counts and timestamps."""
    with _db_lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT session_id, COUNT(*) AS message_count, "
            "MIN(timestamp) AS started, MAX(timestamp) AS last_active "
            "FROM conversations GROUP BY session_id ORDER BY last_active DESC"
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def save_memory(key: str, value: any) -> None:
    """Save or update a key-value memory."""
    with _db_lock:
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO memories (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()


def get_memory(key: str, default=None):
    """Retrieve a memory by key."""
    with _db_lock:
        conn = get_db()
        row = conn.execute("SELECT value FROM memories WHERE key = ?", (key,)).fetchone()
        conn.close()
    
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return row["value"]


def get_all_memories() -> Dict:
    """Return all long-term memories."""
    with _db_lock:
        conn = get_db()
        rows = conn.execute("SELECT key, value, updated_at FROM memories ORDER BY key").fetchall()
        conn.close()

    memories = {}
    for row in rows:
        value = row["value"]
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
        memories[row["key"]] = {"value": value, "updated_at": row["updated_at"]}
    return memories


def delete_memory(key: str) -> bool:
    """Delete a memory key."""
    with _db_lock:
        conn = get_db()
        cur = conn.execute("DELETE FROM memories WHERE key = ?", (key,))
        conn.commit()
        deleted = cur.rowcount > 0
        conn.close()
    return deleted


def save_image_metadata(session_id: str, filename: str, prompt: str, engine: str) -> None:
    """Save image generation metadata."""
    with _db_lock:
        conn = get_db()
        conn.execute(
            "INSERT INTO images (session_id, filename, prompt, engine) VALUES (?, ?, ?, ?)",
            (session_id, filename, prompt, engine)
        )
        conn.commit()
        conn.close()


def get_session_images(session_id: str, limit: int = 50) -> List[Dict]:
    """Get images generated in a session."""
    with _db_lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT filename, prompt, engine, timestamp FROM images "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        conn.close()
    
    return [dict(r) for r in rows]
