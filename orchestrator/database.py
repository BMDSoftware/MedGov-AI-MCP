"""
SQLite database for persisting sessions, uploaded files, and inference jobs.
Uses Python's built-in sqlite3 - zero external dependencies.
"""

import sqlite3
import json
import uuid
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
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

        CREATE TABLE IF NOT EXISTS inference_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            file_id INTEGER REFERENCES uploaded_files(id),
            model_name TEXT,
            status TEXT DEFAULT 'queued',
            result TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
    """)
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


# --- Inference Jobs ---

def create_inference_job(session_id: str, file_id: int, model_name: str) -> int:
    """Queue an inference job. Returns the job ID."""
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO inference_jobs (session_id, file_id, model_name, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
        (session_id, file_id, model_name, datetime.now().isoformat())
    )
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id


def update_inference_job(job_id: int, status: str, result: Optional[Dict] = None, error: Optional[str] = None):
    """Update an inference job's status and result."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    completed = now if status in ("done", "failed") else None
    conn.execute(
        "UPDATE inference_jobs SET status = ?, result = ?, error = ?, completed_at = ? WHERE id = ?",
        (status, json.dumps(result) if result else None, error, completed, job_id)
    )
    conn.commit()
    conn.close()


def get_session_jobs(session_id: str) -> List[Dict]:
    """Get all inference jobs for a session."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM inference_jobs WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        if d.get("result"):
            d["result"] = json.loads(d["result"])
        results.append(d)
    return results


def get_pending_jobs() -> List[Dict]:
    """Get all queued inference jobs (for background worker)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ij.*, uf.stored_path, uf.original_name FROM inference_jobs ij "
        "JOIN uploaded_files uf ON ij.file_id = uf.id "
        "WHERE ij.status = 'queued' ORDER BY ij.created_at"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
