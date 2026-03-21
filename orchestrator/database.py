"""
SQLite database for persisting sessions, uploaded files, and background tasks.
Uses Python's built-in sqlite3 - zero external dependencies.
"""

import sqlite3
import json
import uuid
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "healthmcp.db"
UPLOADS_DIR = DB_DIR / "uploads"


def _get_conn() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist. Called once on backend startup."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT,
            patient_id TEXT,
            patient_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            persisted INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS session_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            tool_name TEXT NOT NULL,
            result_summary TEXT,
            key_data TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            file_type TEXT,
            file_size INTEGER,
            uploaded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS background_tasks (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            task_type TEXT NOT NULL,
            description TEXT NOT NULL,
            input_data TEXT,
            status TEXT DEFAULT 'queued',
            result TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS watched_directories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            custom_prompt TEXT,
            allowed_tools TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
    """)
    # Migration: add allowed_tools to existing databases
    try:
        conn.execute("ALTER TABLE watched_directories ADD COLUMN allowed_tools TEXT")
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


# --- Sessions ---

def create_session(name: Optional[str] = None, patient_id: Optional[str] = None, patient_name: Optional[str] = None) -> str:
    """Create a new session. Returns the session ID."""
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    if not name:
        name = f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    conn = _get_conn()
    conn.execute(
        "INSERT INTO sessions (id, name, patient_id, patient_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, name, patient_id, patient_name, now, now)
    )
    conn.commit()
    conn.close()
    print(f"Created session: {name} ({session_id[:8]}...)")
    return session_id


def list_sessions(persisted_only: bool = False) -> List[Dict]:
    """List all sessions, optionally only persisted ones."""
    conn = _get_conn()
    if persisted_only:
        rows = conn.execute("SELECT * FROM sessions WHERE persisted = 1 ORDER BY updated_at DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session(session_id: str) -> Optional[Dict]:
    """Get a single session by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_session(session_id: str, name: Optional[str] = None, persisted: Optional[bool] = None,
                   patient_id: Optional[str] = None, patient_name: Optional[str] = None):
    """Update session fields."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    updates = ["updated_at = ?"]
    params = [now]

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if persisted is not None:
        updates.append("persisted = ?")
        params.append(1 if persisted else 0)
    if patient_id is not None:
        updates.append("patient_id = ?")
        params.append(patient_id)
    if patient_name is not None:
        updates.append("patient_name = ?")
        params.append(patient_name)

    params.append(session_id)
    conn.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_session(session_id: str):
    """Delete a session and all related data. Files on disk are also removed."""
    conn = _get_conn()
    # Get files to delete from disk
    files = conn.execute("SELECT stored_path FROM uploaded_files WHERE session_id = ?", (session_id,)).fetchall()
    for f in files:
        try:
            os.unlink(f["stored_path"])
        except OSError:
            pass

    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# --- Session Context ---

def save_context_entry(session_id: str, tool_name: str, result_summary: str, key_data: Dict, timestamp: str):
    """Save a single context entry to the database."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO session_context (session_id, tool_name, result_summary, key_data, timestamp) VALUES (?, ?, ?, ?, ?)",
        (session_id, tool_name, result_summary, json.dumps(key_data), timestamp)
    )
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (datetime.now().isoformat(), session_id))
    conn.commit()
    conn.close()


def load_session_context(session_id: str) -> List[Dict]:
    """Load all context entries for a session."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT tool_name, result_summary, key_data, timestamp FROM session_context WHERE session_id = ? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()

    entries = []
    for row in rows:
        entries.append({
            "tool": row["tool_name"],
            "summary": row["result_summary"],
            "data": json.loads(row["key_data"]) if row["key_data"] else {},
            "timestamp": row["timestamp"]
        })
    return entries


def clear_session_context(session_id: str):
    """Clear all context entries for a session."""
    conn = _get_conn()
    conn.execute("DELETE FROM session_context WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# --- Conversation Messages ---

def save_message(session_id: str, role: str, content: str):
    """Save a conversation message (role: 'user' or 'assistant')."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO conversation_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now().isoformat())
    )
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (datetime.now().isoformat(), session_id))
    conn.commit()
    conn.close()


def get_messages(session_id: str) -> List[Dict]:
    """Load all conversation messages for a session in order."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content, timestamp FROM conversation_messages WHERE session_id = ? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"], "timestamp": row["timestamp"]} for row in rows]


def clear_messages(session_id: str):
    """Delete all conversation messages for a session."""
    conn = _get_conn()
    conn.execute("DELETE FROM conversation_messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# --- Uploaded Files ---

def save_uploaded_file(session_id: str, original_name: str, stored_path: str, file_type: str, file_size: int) -> int:
    """Track an uploaded file in the database. Returns the file ID."""
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO uploaded_files (session_id, original_name, stored_path, file_type, file_size, uploaded_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, original_name, stored_path, file_type, file_size, datetime.now().isoformat())
    )
    file_id = cursor.lastrowid
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (datetime.now().isoformat(), session_id))
    conn.commit()
    conn.close()
    return file_id


def remove_session_dirs(session_id: str):
    """Remove ALL dicom_dir entries for a session."""
    conn = _get_conn()
    conn.execute(
        "DELETE FROM uploaded_files WHERE session_id = ? AND file_type = 'dicom_dir'",
        (session_id,)
    )
    conn.commit()
    conn.close()


def remove_session_dir(session_id: str, dir_path: str):
    """Remove a specific dicom_dir entry by stored path."""
    conn = _get_conn()
    conn.execute(
        "DELETE FROM uploaded_files WHERE session_id = ? AND file_type = 'dicom_dir' AND stored_path = ?",
        (session_id, dir_path)
    )
    conn.commit()
    conn.close()


def get_session_total_size(session_id: str) -> int:
    """Get total file size in bytes for a session."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(file_size), 0) as total FROM uploaded_files WHERE session_id = ?",
        (session_id,)
    ).fetchone()
    conn.close()
    return row["total"]


def get_session_files(session_id: str) -> List[Dict]:
    """Get all uploaded files for a session."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM uploaded_files WHERE session_id = ? ORDER BY uploaded_at",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_file(file_id: int) -> Optional[Dict]:
    """Get a single file by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM uploaded_files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Background Tasks ---

def create_task(session_id: str, task_type: str, description: str, input_data: Dict) -> str:
    """Create a background task record. Returns the task ID (UUID)."""
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO background_tasks (id, session_id, task_type, description, input_data, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'queued', ?)",
        (task_id, session_id, task_type, description, json.dumps(input_data), now)
    )
    conn.commit()
    conn.close()
    return task_id


def update_task(task_id: str, status: str, result: Optional[Dict] = None, error: Optional[str] = None):
    """Update a background task's status, result, and completion time."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    completed = now if status in ("done", "failed") else None
    conn.execute(
        "UPDATE background_tasks SET status = ?, result = ?, error = ?, completed_at = ? WHERE id = ?",
        (status, json.dumps(result) if result is not None else None, error, completed, task_id)
    )
    conn.commit()
    conn.close()


def get_task(task_id: str) -> Optional[Dict]:
    """Get a single background task by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM background_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("input_data"):
        d["input_data"] = json.loads(d["input_data"])
    if d.get("result"):
        d["result"] = json.loads(d["result"])
    return d


def list_tasks(session_id: Optional[str] = None) -> List[Dict]:
    """List background tasks, optionally filtered by session. Newest first."""
    conn = _get_conn()
    if session_id:
        rows = conn.execute(
            "SELECT * FROM background_tasks WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM background_tasks ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        if d.get("input_data"):
            d["input_data"] = json.loads(d["input_data"])
        if d.get("result"):
            d["result"] = json.loads(d["result"])
        results.append(d)
    return results


# --- Watched Directories ---

def _parse_watched_directory(row) -> Dict:
    d = dict(row)
    if d.get("allowed_tools"):
        d["allowed_tools"] = json.loads(d["allowed_tools"])
    else:
        d["allowed_tools"] = None
    return d


def create_watched_directory(name: str, path: str, custom_prompt: Optional[str] = None,
                              allowed_tools: Optional[List[str]] = None) -> str:
    dir_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO watched_directories (id, name, path, custom_prompt, allowed_tools, enabled, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
        (dir_id, name, path, custom_prompt, json.dumps(allowed_tools) if allowed_tools is not None else None, now)
    )
    conn.commit()
    conn.close()
    return dir_id


def list_watched_directories() -> List[Dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM watched_directories ORDER BY created_at").fetchall()
    conn.close()
    return [_parse_watched_directory(row) for row in rows]


def get_watched_directory(dir_id: str) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM watched_directories WHERE id = ?", (dir_id,)).fetchone()
    conn.close()
    return _parse_watched_directory(row) if row else None


def update_watched_directory(dir_id: str, name: Optional[str] = None, path: Optional[str] = None,
                              custom_prompt: Optional[str] = None, enabled: Optional[bool] = None,
                              allowed_tools: Optional[List[str]] = None, clear_allowed_tools: bool = False):
    conn = _get_conn()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if path is not None:
        updates.append("path = ?")
        params.append(path)
    if custom_prompt is not None:
        updates.append("custom_prompt = ?")
        params.append(custom_prompt)
    if enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if enabled else 0)
    if allowed_tools is not None:
        updates.append("allowed_tools = ?")
        params.append(json.dumps(allowed_tools))
    elif clear_allowed_tools:
        updates.append("allowed_tools = ?")
        params.append(None)
    if not updates:
        conn.close()
        return
    params.append(dir_id)
    conn.execute(f"UPDATE watched_directories SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_watched_directory(dir_id: str):
    conn = _get_conn()
    conn.execute("DELETE FROM watched_directories WHERE id = ?", (dir_id,))
    conn.commit()
    conn.close()
