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
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
            message TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS watched_directories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            workspace_path TEXT,
            custom_prompt TEXT,
            allowed_tools TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            user_id TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_tool_settings (
            user_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (user_id, tool_name)
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            mode TEXT NOT NULL DEFAULT 'normal',
            llm_mode TEXT NOT NULL DEFAULT 'stateful',
            confirmation INTEGER NOT NULL DEFAULT 1
        );
    """)
    # Migrations: add columns to existing databases
    for table, col_def in [
        ("watched_directories", "allowed_tools TEXT"),
        ("watched_directories", "user_id TEXT"),
        ("watched_directories", "workspace_path TEXT"),
        ("sessions", "user_id TEXT"),
        ("background_tasks", "message TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            conn.commit()
        except Exception:
            pass  # Column already exists
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


# --- Users ---

def create_user(username: str, email: str, password_hash: str) -> str:
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO users (id, username, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, email, password_hash, now)
    )
    conn.commit()
    conn.close()
    return user_id


def get_user_by_username(username: str) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- User Tool Settings ---

def set_tool_enabled(user_id: str, tool_name: str, enabled: bool):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO user_tool_settings (user_id, tool_name, enabled) VALUES (?, ?, ?)",
        (user_id, tool_name, 1 if enabled else 0)
    )
    conn.commit()
    conn.close()


def get_disabled_tools_for_user(user_id: str) -> List[str]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT tool_name FROM user_tool_settings WHERE user_id = ? AND enabled = 0",
        (user_id,)
    ).fetchall()
    conn.close()
    return [row["tool_name"] for row in rows]


# --- User Settings ---

_USER_SETTINGS_DEFAULTS = {"mode": "normal", "llm_mode": "stateful", "confirmation": True}

def get_user_settings(user_id: str) -> dict:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return dict(_USER_SETTINGS_DEFAULTS)
    return {
        "mode": row["mode"],
        "llm_mode": row["llm_mode"],
        "confirmation": bool(row["confirmation"]),
    }


def upsert_user_settings(user_id: str, **kwargs) -> dict:
    current = get_user_settings(user_id)
    current.update(kwargs)
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (user_id, mode, llm_mode, confirmation) VALUES (?, ?, ?, ?)",
        (user_id, current["mode"], current["llm_mode"], 1 if current["confirmation"] else 0)
    )
    conn.commit()
    conn.close()
    return current


# --- Sessions ---

def create_session(name: Optional[str] = None, patient_id: Optional[str] = None, patient_name: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """Create a new session. Returns the session ID."""
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    if not name:
        name = f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    conn = _get_conn()
    conn.execute(
        "INSERT INTO sessions (id, name, patient_id, patient_name, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, name, patient_id, patient_name, now, now, user_id)
    )
    conn.commit()
    conn.close()
    print(f"Created session: {name} ({session_id[:8]}...)")
    return session_id


def list_sessions(persisted_only: bool = False, user_id: Optional[str] = None) -> List[Dict]:
    """List sessions, optionally filtered by user and/or persisted status."""
    conn = _get_conn()
    if user_id and persisted_only:
        rows = conn.execute("SELECT * FROM sessions WHERE user_id = ? AND persisted = 1 ORDER BY updated_at DESC", (user_id,)).fetchall()
    elif user_id:
        rows = conn.execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
    elif persisted_only:
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

    log_file = Path(__file__).parent / "logs" / f"agenticagent_debug_{session_id}.txt"
    try:
        log_file.unlink(missing_ok=True)
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


def update_task(task_id: str, status: str, result: Optional[Dict] = None, error: Optional[str] = None, message: Optional[str] = None):
    """Update a background task's status, result, completion time, and optional progress message."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    completed = now if status in ("done", "failed") else None
    conn.execute(
        "UPDATE background_tasks SET status = ?, result = ?, error = ?, message = ?, completed_at = ? WHERE id = ?",
        (status, json.dumps(result) if result is not None else None, error, message, completed, task_id)
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


def list_tasks(session_id: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict]:
    """List background tasks, optionally filtered by session and/or user. Newest first."""
    conn = _get_conn()
    if session_id and user_id is not None:
        rows = conn.execute(
            "SELECT background_tasks.* FROM background_tasks "
            "JOIN sessions ON background_tasks.session_id = sessions.id "
            "WHERE background_tasks.session_id = ? AND sessions.user_id = ? "
            "ORDER BY background_tasks.created_at DESC",
            (session_id, user_id)
        ).fetchall()
    elif session_id:
        rows = conn.execute(
            "SELECT * FROM background_tasks WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,)
        ).fetchall()
    elif user_id is not None:
        rows = conn.execute(
            "SELECT background_tasks.* FROM background_tasks "
            "JOIN sessions ON background_tasks.session_id = sessions.id "
            "WHERE sessions.user_id = ? "
            "ORDER BY background_tasks.created_at DESC",
            (user_id,)
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
                              allowed_tools: Optional[List[str]] = None,
                              user_id: Optional[str] = None,
                              workspace_path: Optional[str] = None) -> str:
    dir_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO watched_directories (id, name, path, workspace_path, custom_prompt, allowed_tools, enabled, created_at, user_id) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (dir_id, name, path, workspace_path, custom_prompt, json.dumps(allowed_tools) if allowed_tools is not None else None, now, user_id)
    )
    conn.commit()
    conn.close()
    return dir_id


def create_default_workspaces(user_id: str, username: str, workspaces_root: str) -> None:
    """Create the ROI and CELLPOSE sample workspaces for a newly registered user."""
    cellpose_workspace = os.path.join(workspaces_root, username, "cellpose")
    cellpose_incoming = os.path.join(cellpose_workspace, "incoming")
    os.makedirs(cellpose_incoming, exist_ok=True)
    create_watched_directory(
        name="CELLPOSE",
        path=cellpose_incoming,
        workspace_path=cellpose_workspace,
        custom_prompt="Do nothing, just a placeholder for images.",
        user_id=user_id,
    )

    roi_workspace = os.path.join(workspaces_root, username, "roi")
    roi_incoming = os.path.join(roi_workspace, "incoming")
    os.makedirs(roi_incoming, exist_ok=True)
    roi_prompt = (
        f"When a new file arrives, check whether it is a pathology ROI image. "
        f"If it is, run Cellpose cell segmentation and count the cells. "
        f"If the cell count exceeds 2000, copy the segmentation mask to the output folder at "
        f"{cellpose_workspace} and log the result. "
        f"If the file is not a valid ROI image, move it to the uncertain folder."
    )
    create_watched_directory(
        name="ROI",
        path=roi_incoming,
        workspace_path=roi_workspace,
        custom_prompt=roi_prompt,
        user_id=user_id,
    )


def list_watched_directories(user_id: Optional[str] = None) -> List[Dict]:
    """List watched directories, filtered by user_id when provided."""
    conn = _get_conn()
    if user_id:
        rows = conn.execute("SELECT * FROM watched_directories WHERE user_id = ? ORDER BY created_at", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM watched_directories ORDER BY created_at").fetchall()
    conn.close()
    return [_parse_watched_directory(row) for row in rows]


def list_watched_directories_all() -> List[Dict]:
    """List all watched directories regardless of owner. Used internally by watcher startup."""
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
                              allowed_tools: Optional[List[str]] = None, clear_allowed_tools: bool = False,
                              workspace_path: Optional[str] = None):
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
    if workspace_path is not None:
        updates.append("workspace_path = ?")
        params.append(workspace_path)
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
