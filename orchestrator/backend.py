#!/usr/bin/env python3
import asyncio
import json
import os
import re
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict
from pathlib import Path
from dotenv import load_dotenv

# Load env BEFORE importing agent so LLM_BACKEND is set
load_dotenv()

# Tee stdout to a startup log so MCP server errors are visible via /api/logs/startup
_startup_log_path = Path(__file__).parent / "logs" / "startup.log"
_startup_log_path.parent.mkdir(exist_ok=True)

class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            try:
                s.write(data)
            except Exception:
                pass

    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass

    def fileno(self):
        return self._streams[0].fileno()

    def isatty(self):
        return False

_startup_log_file = open(_startup_log_path, "w", buffering=1, encoding="utf-8")
sys.stdout = _Tee(sys.__stdout__, _startup_log_file)
sys.stderr = _Tee(sys.__stderr__, _startup_log_file)

from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from contextlib import asynccontextmanager
from agent import AgenticAgent
from agent.stm import STM_BUILTIN_TOOLS
import database as db
import task_runner
from watcher_service import watcher_service
import auth
from auth import get_current_user

_shutdown_event: Optional[asyncio.Event] = None
_mcp_notifications: list = []  # in-memory MCP event log

# Root directory for auto-generated workspace folders.
# Defaults to /app/workspaces (the Docker mount); override via WORKSPACES_ROOT in .env for local dev.
WORKSPACES_ROOT = os.environ.get("WORKSPACES_ROOT", "/workspaces")

# --- Per-user state ---

@dataclass
class UserState:
    current_session_id: Optional[str] = None
    uploaded_files: list = field(default_factory=list)
    temp_file_paths: dict = field(default_factory=dict)
    uploaded_dirs: list = field(default_factory=list)
    image_metadata: dict = field(default_factory=lambda: {"modality": None, "bodyPart": None})

_user_states: Dict[str, UserState] = {}
_agents: Dict[str, AgenticAgent] = {}
_agents_lock = asyncio.Lock()

# Cellpose v4 only uses cpsam; the restoration/training/listing tools from cellpose-mcp
# are not needed and add ~1,500 tokens to every Gemini prompt, increasing latency.
_DEFAULT_DISABLED_TOOLS = {
    "cellpose.denoise_image",
    "cellpose.deblur_image",
    "cellpose.upsample_image",
    "cellpose.restore_and_segment",
    "cellpose.train_segmentation_model",
    "cellpose.list_available_models",
    "cellpose.estimate_cell_diameter",
    "cellpose.save_masks",
    "cellpose.load_image_info",
}


def _get_user_state(user_id: str) -> UserState:
    if user_id not in _user_states:
        _user_states[user_id] = UserState()
    return _user_states[user_id]


async def get_or_create_agent(user_id: str) -> AgenticAgent:
    """Return the existing agent for this user, or lazily create and initialise one."""
    async with _agents_lock:
        if user_id not in _agents:
            agent = AgenticAgent()
            await agent._initialize_components()
            # Apply this user's disabled tools from DB, then system-level defaults
            disabled = db.get_disabled_tools_for_user(user_id)
            for t in disabled:
                agent.agent_tools.discard(t)
            for t in _DEFAULT_DISABLED_TOOLS:
                agent.agent_tools.discard(t)
            agent._refresh_agent_components()
            agent.set_mode(_app_settings.get("mode", "normal"))
            # Re-apply saved confirmation override (set_mode resets it to mode default)
            if "confirmation" in _app_settings:
                agent.require_confirmation = _app_settings["confirmation"]
            _agents[user_id] = agent
        return _agents[user_id]


def _push_notification(event_type: str, message: str):
    from datetime import datetime
    _mcp_notifications.append({
        "type": event_type,
        "message": message,
        "timestamp": datetime.now().isoformat()
    })
    if len(_mcp_notifications) > 100:
        _mcp_notifications.pop(0)

# --- App settings (persisted to disk) ---
_SETTINGS_FILE = Path(__file__).parent / "app_settings.json"

def _load_settings() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {"mode": "debug"}

def _save_settings(settings: dict):
    try:
        _SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
    except Exception as e:
        print(f"[settings] Failed to save: {e}")

_app_settings = _load_settings()


async def _poll_mcp_tools(interval: int = 300):
    """Periodically re-query all connected MCP servers for tool changes across all user agents."""
    while True:
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=interval)
            return  # shutdown signalled
        except asyncio.TimeoutError:
            pass
        try:
            async with _agents_lock:
                agents_snapshot = list(_agents.values())
            for agent in agents_snapshot:
                try:
                    servers = list(agent.tool_registry.sessions.keys())
                    tools_changed = False
                    for name in servers:
                        try:
                            old_keys = set(k for k in agent.available_tools if k.startswith(f"{name}."))
                            new_tools = await agent.tool_registry.refresh_server_tools(name)
                            new_keys = set(new_tools.keys())
                            added = new_keys - old_keys
                            removed = old_keys - new_keys
                            for k in old_keys:
                                agent.available_tools.pop(k, None)
                                agent.agent_tools.discard(k)
                            agent.available_tools.update(new_tools)
                            agent.agent_tools.update(new_keys)
                            agent.agent_tools -= _DEFAULT_DISABLED_TOOLS
                            for k in added:
                                _push_notification("tool_added", f"New tool available: {k}")
                                tools_changed = True
                            for k in removed:
                                _push_notification("tool_removed", f"Tool removed: {k}")
                                tools_changed = True
                        except Exception:
                            pass
                    if tools_changed:
                        agent._refresh_agent_components()
                except Exception:
                    pass
        except Exception:
            pass


async def _watcher_execute(dir_id: str, files: list):
    """Called by watcher_service when new files are detected in a watched directory."""
    wd = db.get_watched_directory(dir_id)
    if not wd or not wd["enabled"]:
        return

    user_id = wd.get("user_id")
    if not user_id:
        watcher_service.push_console(dir_id, "[WARN] Workspace has no owner, skipping.")
        return

    agent = await get_or_create_agent(user_id)
    state = _get_user_state(user_id)
    if not state.current_session_id:
        state.current_session_id = db.create_session(name="Watcher Session", user_id=user_id)

    workspace_path = wd.get("workspace_path") or wd["path"]

    # Copy files from the (possibly read-only) watched directory into the workspace
    # before handing paths to the agent, which needs a writable location.
    # Files already inside workspace_path (e.g. from cross-workspace triggers) are
    # passed through unchanged — computing relpath against wd["path"] would be wrong.
    incoming_dir = os.path.join(workspace_path, "incoming")
    os.makedirs(incoming_dir, exist_ok=True)
    copied_files = []
    norm_ws = os.path.normpath(workspace_path) + os.sep
    for src in files:
        if os.path.normpath(src).startswith(norm_ws):
            # Already inside this workspace — no copy needed
            copied_files.append(src)
            continue
        try:
            rel = os.path.relpath(src, wd["path"])
            dst = os.path.join(incoming_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied_files.append(dst)
        except Exception as e:
            watcher_service.push_console(dir_id, f"[WARN] Could not copy {os.path.basename(src)} to workspace: {e}")
    if not copied_files:
        watcher_service.push_console(dir_id, "[ERROR] No files could be copied to workspace, aborting.")
        return
    files = copied_files

    file_list = "\n".join(f"  - {f}" for f in files)
    custom = (wd.get("custom_prompt") or "").strip()

    if custom:
        goal = (
            f"New file(s) detected in watched folder '{wd['name']}'.\n\n"
            f"Files (already copied to workspace):\n{file_list}\n\n"
            f"Workspace directory: {workspace_path}\n\n"
            f"{custom}"
        )
    else:
        goal = (
            f"New file(s) detected in watched folder '{wd['name']}'.\n\n"
            f"Files (already copied to workspace inbox):\n{file_list}\n\n"
            f"Workspace directory: {workspace_path}\n\n"
            "Your job is to CLASSIFY and ORGANIZE these files only. Do NOT run analysis or inference unless explicitly instructed.\n\n"
            "Steps:\n"
            "1. Check if each file is a DICOM, NIfTI, or other medical imaging format using the available parse tools.\n"
            "2. Based on the file type, move it to the appropriate subdirectory inside the workspace directory:\n"
            f"   - DICOM → '{workspace_path}/dicom/'\n"
            f"   - NIfTI (.nii, .nii.gz) → '{workspace_path}/nifti/'\n"
            f"   - Unknown or unreadable → '{workspace_path}/uncertain/'\n"
            "3. Write a brief one-line note alongside each file if helpful.\n"
            "Do NOT call analyze_image or run_inference. Classification and organization is the only goal."
        )

    # Snapshot other workspaces so we can detect cross-workspace file moves after the AI runs
    other_wds = [
        w for w in db.list_watched_directories_all()
        if w["id"] != dir_id and w.get("enabled") and w.get("workspace_path")
        and os.path.isdir(w["workspace_path"])
    ]
    snapshots = {
        w["id"]: {str(p) for p in Path(w["workspace_path"]).rglob("*") if p.is_file()}
        for w in other_wds
    }

    watcher_service.push_console(dir_id, "[AI] Starting autonomous analysis...")
    agent.set_agent_type(True)
    original_require_confirmation = agent.require_confirmation
    agent.require_confirmation = False
    allowed_tools = wd.get("allowed_tools")
    original_agent_tools = set(agent.agent_tools)
    if allowed_tools is not None:
        agent.agent_tools = original_agent_tools & set(allowed_tools)
    else:
        agent.agent_tools = original_agent_tools.copy()
    # Workspace execution is already a background job — sub-queuing tasks means the
    # agent can't act on results (e.g. routing by cell count). Force direct tool calls.
    agent.agent_tools.discard("queue_task")
    agent._refresh_agent_components()
    try:
        # Do NOT pass fileList — workspace files are text/DICOM, not vision inputs.
        # The agent must use read_file / parse_dicom tools via the paths in the goal prompt.
        # Passing fileList with b"" contents causes Gemini to say it can't access the file
        # and hallucinate the original watched-directory path from session context.
        # Give the agent enough iterations to handle every file: 3 per file (segment + decide + move)
        # plus a fixed overhead of 5 for any list/init steps. Minimum 20.
        max_iter = max(20, len(files) * 3 + 5)
        result = await agent.execute_task(goal, max_iterations=max_iter, session_id=state.current_session_id, user_id=user_id)
    except Exception as e:
        watcher_service.push_console(dir_id, f"[ERROR] AI execution failed: {e}")
        return
    finally:
        agent.set_agent_type(False)
        agent.require_confirmation = original_require_confirmation
        agent.agent_tools = original_agent_tools
        agent._refresh_agent_components()
    if result and result.get("answer"):
        watcher_service.push_console(dir_id, f"[AI] {result['answer']}")
    watcher_service.push_console(dir_id, "[AI] Analysis complete.")

    # Trigger any workspace that received new files as a result of this task
    for w in other_wds:
        current = {str(p) for p in Path(w["workspace_path"]).rglob("*") if p.is_file()}
        new_files = sorted(current - snapshots.get(w["id"], set()))
        if new_files:
            watcher_service.push_console(w["id"], f"[INFO] {len(new_files)} file(s) received from '{wd['name']}', triggering AI...")
            asyncio.create_task(_watcher_execute(w["id"], new_files))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    # Startup
    db.init_db()
    task_runner.init()
    asyncio.create_task(_poll_mcp_tools(120))

    # Start watcher service and resume all enabled watched directories
    watcher_service.set_execute_callback(_watcher_execute)
    await watcher_service.start()
    for wd in db.list_watched_directories_all():
        if wd["enabled"]:
            watcher_service.start_watching(wd["id"], wd["path"], wd["name"])
    try:
        yield
    except asyncio.CancelledError:
        task = asyncio.current_task()
        if task is not None:
            task.uncancel()
    finally:
        _shutdown_event.set()
        await watcher_service.stop()
        async with _agents_lock:
            agents_snapshot = list(_agents.values())
        for agent in agents_snapshot:
            try:
                await agent.close()
            except BaseException:
                pass

_OPENAPI_TAGS = [
    {"name": "agent", "description": "AI agent query processing, tool management, and patient context"},
    {"name": "files", "description": "Medical image file and directory upload/management"},
    {"name": "sessions", "description": "Session lifecycle, persistence, and context restore"},
    {"name": "monai", "description": "Direct MONAI tool calls — bypasses the AI agent (used by the Test tab)"},
    {"name": "events", "description": "Server-Sent Events stream and background task status"},
    {"name": "system", "description": "Health check, application mode, and settings"},
]

app = FastAPI(
    title="Agentic Health Assistant API",
    description=(
        "REST API for the AgenticHealthMCP orchestrator. "
        "Provides AI agent querying, medical image management, "
        "MONAI inference pipeline, and session management."
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=_OPENAPI_TAGS,
)


_default_origins = "http://localhost:5173,http://localhost:3000,http://localhost,http://localhost:80"
_cors_origins_env = os.getenv("CORS_ORIGINS", _default_origins)
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/auth/register", tags=["auth"], summary="Register a new user account")
async def register(data: dict = Body(...)):
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not username or not email or not password:
        raise HTTPException(400, "username, email, and password are required")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.get_user_by_username(username):
        raise HTTPException(409, "Username already taken")
    if db.get_user_by_email(email):
        raise HTTPException(409, "Email already registered")
    hashed = auth.hash_password(password)
    user_id = db.create_user(username, email, hashed)
    token = auth.create_access_token(user_id, username)
    return {"access_token": token, "token_type": "bearer", "user_id": user_id, "username": username}


@app.post("/api/auth/login", tags=["auth"], summary="Login and receive a JWT token")
async def login(data: dict = Body(...)):
    username = data.get("username") or ""
    password = data.get("password") or ""
    user = db.get_user_by_username(username)
    if not user or not auth.verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = auth.create_access_token(user["id"], user["username"])
    return {"access_token": token, "token_type": "bearer", "user_id": user["id"], "username": user["username"]}


@app.get("/api/auth/me", tags=["auth"], summary="Get current user info")
async def me(current_user: dict = Depends(get_current_user)):
    user = db.get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(404, "User not found")
    return {"user_id": user["id"], "username": user["username"], "email": user["email"]}


@app.post("/api/set-metadata", tags=["files"], summary="Set image modality and body part metadata")
async def set_metadata(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    state = _get_user_state(current_user["user_id"])
    state.image_metadata["modality"] = data.get("modality")
    state.image_metadata["bodyPart"] = data.get("bodyPart")
    return {"status": "ok"}


@app.get("/api/mode", tags=["system"], summary="Get current UI mode (debug or normal)")
async def get_mode(current_user: dict = Depends(get_current_user)):
    return {"mode": _app_settings.get("mode", "normal")}

@app.post("/api/mode", tags=["system"], summary="Set UI mode — 'debug' shows tool calls, 'normal' uses clinical language")
async def set_mode(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    mode = data.get("mode", "debug")
    if mode not in ("debug", "normal"):
        raise HTTPException(status_code=400, detail="mode must be 'debug' or 'normal'")
    if mode == _app_settings.get("mode"):
        return {"mode": mode}
    _app_settings["mode"] = mode
    # Reset confirmation to mode default when switching modes
    if mode == "debug":
        _app_settings["confirmation"] = True
    else:
        _app_settings["confirmation"] = False
    _save_settings(_app_settings)
    async with _agents_lock:
        for agent in _agents.values():
            agent.set_mode(mode)
    return {"mode": mode}

@app.get("/api/confirmation", tags=["system"], summary="Get whether tool confirmation is required")
async def get_confirmation(current_user: dict = Depends(get_current_user)):
    return {"confirmation": _app_settings.get("confirmation", True)}

@app.post("/api/confirmation", tags=["system"], summary="Set tool confirmation (only effective in normal mode)")
async def set_confirmation(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    if _app_settings.get("mode", "normal") == "debug":
        return {"confirmation": True}
    enabled = bool(data.get("confirmation", False))
    _app_settings["confirmation"] = enabled
    _save_settings(_app_settings)
    async with _agents_lock:
        for agent in _agents.values():
            agent.require_confirmation = enabled
    return {"confirmation": enabled}


@app.get("/api/llm-mode", tags=["system"], summary="Get current LLM mode (stateful or stateless)")
async def get_llm_mode(current_user: dict = Depends(get_current_user)):
    return {"llm_mode": _app_settings.get("llm_mode", "stateful")}

@app.post("/api/llm-mode", tags=["system"], summary="Set LLM mode — 'stateful' keeps history, 'stateless' sends each query fresh")
async def set_llm_mode(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    llm_mode = data.get("llm_mode", "stateful")
    if llm_mode not in ("stateful", "stateless"):
        raise HTTPException(status_code=400, detail="llm_mode must be 'stateful' or 'stateless'")
    _app_settings["llm_mode"] = llm_mode
    _save_settings(_app_settings)

    # Refresh active agents so STM built-ins are only exposed in stateless mode.
    stm_tool_names = set(STM_BUILTIN_TOOLS.keys())
    async with _agents_lock:
        for agent in _agents.values():
            if llm_mode == "stateless":
                agent.available_tools.update(STM_BUILTIN_TOOLS)
                agent.agent_tools.update(stm_tool_names)
            else:
                for tool_name in stm_tool_names:
                    agent.available_tools.pop(tool_name, None)
                    agent.agent_tools.discard(tool_name)
            agent._refresh_agent_components()

    return {"llm_mode": llm_mode}
@app.get("/api/logs", tags=["system"], summary="Tail the latest agent debug log or startup log")
async def get_agent_logs(lines: int = 200, source: str = "agent", session_id: str = None, current_user: dict = Depends(get_current_user)):
    import glob as _glob
    log_dir = Path(__file__).parent / "logs"

    if source == "startup":
        log_file = log_dir / "startup.log"
        if not log_file.exists():
            return {"lines": [], "file": None}
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            return {"lines": all_lines[-lines:], "file": "startup.log"}
        except Exception as e:
            return {"lines": [str(e)], "file": None}

    if session_id:
        target = log_dir / f"agenticagent_debug_{session_id}.txt"
        if not target.exists():
            return {"lines": [], "file": None}
        latest = str(target)
    else:
        files = sorted(_glob.glob(str(log_dir / "agenticagent_debug_*.txt")))
        if not files:
            return {"lines": [], "file": None}
        latest = files[-1]
    try:
        with open(latest, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        return {"lines": all_lines[-lines:], "file": Path(latest).name}
    except Exception as e:
        return {"lines": [str(e)], "file": None}


# --- Watched Directories ---

@app.get("/api/watched-directories", tags=["system"], summary="List all watched directories")
async def list_watched_directories(current_user: dict = Depends(get_current_user)):
    dirs = db.list_watched_directories(user_id=current_user["user_id"])
    for d in dirs:
        d["watching"] = watcher_service.is_watching(d["id"])
    return dirs


@app.post("/api/watched-directories", tags=["system"], summary="Add a new watched directory")
async def create_watched_directory(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    name = data.get("name", "").strip()
    path = data.get("path", "").strip()
    custom_prompt = (data.get("custom_prompt") or "").strip() or None
    allowed_tools = data.get("allowed_tools") or None
    if not name or not path:
        raise HTTPException(status_code=400, detail="name and path are required")

    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    workspace_path = os.path.join(WORKSPACES_ROOT, current_user["username"], slug)
    try:
        os.makedirs(workspace_path, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create workspace directory: {e}. Set WORKSPACES_ROOT in .env for local development.")

    dir_id = db.create_watched_directory(name, path, custom_prompt, allowed_tools,
                                         user_id=current_user["user_id"], workspace_path=workspace_path)
    watcher_service.push_console(dir_id, f"[INFO] Directory '{name}' added. Workspace: {workspace_path}")
    wd = db.get_watched_directory(dir_id)
    watcher_service.start_watching(dir_id, wd["path"], wd["name"])
    wd["watching"] = watcher_service.is_watching(dir_id)
    return wd


@app.put("/api/watched-directories/{dir_id}", tags=["system"], summary="Update a watched directory")
async def update_watched_directory(dir_id: str, data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    wd = db.get_watched_directory(dir_id)
    if not wd or wd.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Not found")
    was_watching = watcher_service.is_watching(dir_id)
    allowed_tools = data.get("allowed_tools")
    workspace_path = (data.get("workspace_path") or "").strip() or None
    if workspace_path:
        os.makedirs(workspace_path, exist_ok=True)
    db.update_watched_directory(
        dir_id,
        name=data.get("name"),
        path=data.get("path"),
        custom_prompt=data.get("custom_prompt"),
        enabled=data.get("enabled"),
        allowed_tools=allowed_tools if allowed_tools else None,
        clear_allowed_tools=("allowed_tools" in data and not allowed_tools),
        workspace_path=workspace_path,
    )
    wd = db.get_watched_directory(dir_id)
    # Restart watcher if path changed while active
    if was_watching and data.get("path"):
        watcher_service.stop_watching(dir_id)
        watcher_service.start_watching(dir_id, wd["path"], wd["name"])
    # Handle enable/disable
    if "enabled" in data:
        if data["enabled"] and not watcher_service.is_watching(dir_id):
            watcher_service.start_watching(dir_id, wd["path"], wd["name"])
        elif not data["enabled"] and watcher_service.is_watching(dir_id):
            watcher_service.stop_watching(dir_id)
    wd["watching"] = watcher_service.is_watching(dir_id)
    return wd


@app.delete("/api/watched-directories/{dir_id}", tags=["system"], summary="Remove a watched directory")
async def delete_watched_directory(dir_id: str, current_user: dict = Depends(get_current_user)):
    wd = db.get_watched_directory(dir_id)
    if not wd or wd.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Not found")
    watcher_service.stop_watching(dir_id)
    workspace_path = wd.get("workspace_path")
    db.delete_watched_directory(dir_id)
    if workspace_path and os.path.isdir(workspace_path):
        shutil.rmtree(workspace_path, ignore_errors=True)
    return {"status": "deleted"}


@app.get("/api/watched-directories/{dir_id}/console", tags=["system"], summary="Get console log for a watched directory")
async def get_directory_console(dir_id: str, current_user: dict = Depends(get_current_user)):
    wd = db.get_watched_directory(dir_id)
    if not wd or wd.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Not found")
    return watcher_service.get_console_log(dir_id)


@app.post("/api/watched-directories/{dir_id}/import-files",
          tags=["system"],
          summary="Import files directly into a workspace directory (debug mode)")
async def import_files_to_workspace(
    dir_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Upload files directly into a watched directory's path. Preserves relative directory structure."""
    wd = db.get_watched_directory(dir_id)
    if not wd or wd.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Workspace not found")

    workspace_path = Path(wd.get("workspace_path") or wd["path"])
    incoming_dir = workspace_path / "incoming"
    incoming_dir.mkdir(parents=True, exist_ok=True)

    form = await request.form(max_files=10_000, max_fields=10_000)
    files = [v for k, v in form.multi_items() if hasattr(v, 'read')]
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    saved_paths = []
    saved_count = 0
    total_size = 0
    for f in files:
        contents = await f.read()
        rel_path = f.filename or f"file_{saved_count}"
        dest = incoming_dir / rel_path
        # Skip hidden/junk files
        if dest.name.startswith('.') or dest.name == 'DS_Store':
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as out:
            out.write(contents)
        saved_paths.append(str(dest))
        saved_count += 1
        total_size += len(contents)

    watcher_service.push_console(
        dir_id, f"[INFO] Imported {saved_count} files ({total_size} bytes) via debug upload"
    )

    if saved_paths:
        asyncio.create_task(_watcher_execute(dir_id, saved_paths))

    return {"status": "success", "file_count": saved_count, "total_size": total_size, "target_path": str(incoming_dir)}


@app.get("/api/browse-directory", tags=["system"], summary="Browse filesystem directories for the directory picker")
async def browse_directory(path: str = "/", current_user: dict = Depends(get_current_user)):
    path = os.path.abspath(path)
    try:
        entries = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isdir(full) and not name.startswith('.'):
                entries.append({"name": name, "path": full})
        parent = str(Path(path).parent) if path != "/" else "/"
        return {"path": path, "parent": parent, "entries": entries}
    except PermissionError:
        return {"path": path, "parent": str(Path(path).parent), "entries": [], "error": "Permission denied"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/create-directory", tags=["system"], summary="Create a new directory on the filesystem")
async def create_directory(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    path = (data.get("path") or "").strip()
    if not path or not os.path.isabs(path):
        raise HTTPException(status_code=400, detail="An absolute path is required")
    try:
        os.makedirs(path, exist_ok=True)
        return {"path": os.path.abspath(path), "created": True}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/set-directory", tags=["files"], summary="Add, remove, or clear registered DICOM series directories")
async def set_directory(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    dir_path = data.get("dir_path")
    remove = data.get("remove", False)

    # Ensure a session exists before writing to the DB
    if not state.current_session_id:
        state.current_session_id = db.create_session(user_id=uid)

    if dir_path is None:
        state.uploaded_dirs.clear()
        db.remove_session_dirs(state.current_session_id)
    elif remove:
        if dir_path in state.uploaded_dirs:
            state.uploaded_dirs.remove(dir_path)
        db.remove_session_dir(state.current_session_id, dir_path)
    else:
        if os.path.isdir(dir_path) and dir_path not in state.uploaded_dirs:
            state.uploaded_dirs.append(dir_path)
            dirname = Path(dir_path).name
            total_size = sum(f.stat().st_size for f in Path(dir_path).iterdir() if f.is_file())
            db.save_uploaded_file(state.current_session_id, dirname, dir_path, 'dicom_dir', total_size)

    return {"status": "ok", "dirs": state.uploaded_dirs}


@app.get("/api/available-models", tags=["agent"], summary="List available Gemini models for the configured API key")
async def available_models(current_user: dict = Depends(get_current_user)):
    try:
        from google import genai as google_genai
        client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        models = [m.name.replace("models/", "") for m in client.models.list() if "generateContent" in (m.supported_actions or [])]
        return {"models": sorted(models)}
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.post("/api/set-model", tags=["agent"], summary="Switch the LLM model for the current session")
async def set_model(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    model_id = data.get("model_id")
    if not model_id:
        return {"error": "model_id is required"}
    agent = await get_or_create_agent(current_user["user_id"])
    if agent.llm_client:
        agent.llm_client.set_model(model_id)
    return {"status": "ok", "model_id": model_id}


@app.get("/api/current-model", tags=["agent"], summary="Get the currently active LLM model")
async def get_current_model(current_user: dict = Depends(get_current_user)):
    agent = await get_or_create_agent(current_user["user_id"])
    model_id = agent.llm_client.model_id if agent.llm_client else os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return {"model_id": model_id}


@app.post("/api/change-agent-type", tags=["agent"], summary="Switch between default and autonomous agent modes")
async def change_agent_type(data: str = Body(...), current_user: dict = Depends(get_current_user)):
    agent = await get_or_create_agent(current_user["user_id"])
    autonomous = data == "autonomous"
    agent.set_agent_type(autonomous=autonomous)
    return {"status": "ok", "agent_type": "autonomous" if autonomous else "default"}


@app.post("/api/process-query", tags=["agent"], summary="Send a natural language query to the AI agent")
async def process_query(query: str = Body(..., media_type="text/plain"), current_user: dict = Depends(get_current_user)):
    """
    Streams the response as newline-delimited JSON so proxies and load
    balancers with short idle timeouts (e.g. 60 s on many cloud platforms)
    don't 504 during long agentic loops.  The frontend reads the stream and
    parses the final JSON line; intermediate lines are SSE-style keepalive
    comments that keep the TCP connection alive.
    """
    print(f"Processing ad-hoc query: {query}")
    uid = current_user["user_id"]
    agent = await get_or_create_agent(uid)
    state = _get_user_state(uid)
    if not state.current_session_id:
        state.current_session_id = db.create_session(user_id=uid)

    async def _run_and_stream():
        try:
            session_files = db.get_session_files(state.current_session_id)

            if not state.uploaded_files and not session_files and not state.uploaded_dirs:
                execute_coro = agent.execute_task(query, session_id=state.current_session_id, user_id=uid)
            else:
                image_data = []
                if state.uploaded_files:
                    for filename, contents in state.uploaded_files:
                        stored_path = state.temp_file_paths.get(filename)
                        if stored_path and os.path.exists(stored_path):
                            image_data.append((stored_path, contents))
                elif session_files:
                    for f in session_files:
                        if f.get("file_type") == "dicom_dir":
                            continue
                        path = f["stored_path"]
                        if os.path.exists(path):
                            with open(path, "rb") as fh:
                                contents = fh.read()
                            image_data.append((path, contents))

                for dir_path in state.uploaded_dirs:
                    if os.path.isdir(dir_path):
                        image_data.append((dir_path, b""))

                if not image_data or all(p == b"" for _, p in image_data):
                    session_dirs = [f for f in session_files if f.get("file_type") == "dicom_dir"]
                    for f in session_dirs:
                        if os.path.isdir(f["stored_path"]) and f["stored_path"] not in state.uploaded_dirs:
                            image_data.append((f["stored_path"], b""))

                if image_data:
                    execute_coro = agent.execute_task(query, fileList=image_data, session_id=state.current_session_id, user_id=uid)
                else:
                    execute_coro = agent.execute_task(query, session_id=state.current_session_id, user_id=uid)

            # Run agent concurrently; emit a keepalive comment every 15 s so
            # upstream proxies with short idle timeouts don't drop the connection.
            task = asyncio.ensure_future(execute_coro)
            while not task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"

            result = task.result()

            db.save_message(state.current_session_id, "user", query)
            if isinstance(result, dict):
                agent_text = result.get("answer") or result.get("response") or result.get("error") or ""
            else:
                agent_text = str(result)
            if agent_text:
                db.save_message(state.current_session_id, "assistant", agent_text)

            yield json.dumps({"result": result}) + "\n"

        except Exception as e:
            print(f"Error processing query: {e}")
            yield json.dumps({"result": {"error": str(e)}}) + "\n"

    return StreamingResponse(
        _run_and_stream(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"},
    )



@app.post("/api/upload", tags=["files"], summary="Upload a single medical image file (.dcm, .nii.gz, etc.)")
async def upload_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    if not state.current_session_id:
        state.current_session_id = db.create_session(user_id=uid)
    print(f"Received file: {file.filename}")
    try:
        contents = await file.read()
        ext = os.path.splitext(file.filename)[1] if not file.filename.endswith('.nii.gz') else '.nii.gz'
        stored_name = f"{uuid.uuid4().hex[:12]}_{file.filename}"
        stored_path = str(db.UPLOADS_DIR / stored_name)

        with open(stored_path, "wb") as f:
            f.write(contents)

        file_type = ext.lstrip('.') or 'unknown'
        file_id = db.save_uploaded_file(state.current_session_id, file.filename, stored_path, file_type, len(contents))

        state.uploaded_files.append((file.filename, contents))
        state.temp_file_paths[file.filename] = stored_path

        print(f"Uploaded {file.filename} -> {stored_path} (file_id={file_id})")
        return {"status": "success", "filename": file.filename, "size": len(contents), "file_id": file_id, "stored_path": stored_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/upload", tags=["files"], summary="Remove an uploaded file from the session")
async def remove_file(filename: str, current_user: dict = Depends(get_current_user)):
    state = _get_user_state(current_user["user_id"])
    print(f"Removing file: {filename}")
    for i, (fname, _) in enumerate(state.uploaded_files):
        if fname == filename:
            del state.uploaded_files[i]
            if filename in state.temp_file_paths:
                try:
                    os.unlink(state.temp_file_paths[filename])
                except Exception:
                    pass
                del state.temp_file_paths[filename]
            return {"status": "success", "message": f"Removed {filename}"}
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/api/upload-directory", tags=["files"], summary="Upload a directory of DICOM slices (multipart, up to 10k files)")
async def upload_directory(request: Request, current_user: dict = Depends(get_current_user)):
    """Upload a directory of medical image files. Supports up to 10k files."""
    form = await request.form(max_files=10_000, max_fields=10_000)
    files = [v for k, v in form.multi_items() if hasattr(v, 'read')]
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    try:
        # Use the first file's relative path to get the directory name
        first_path = files[0].filename or "unknown"
        # Browser sends paths like "dirname/file1" - extract the top-level dir name
        dirname = first_path.split("/")[0] if "/" in first_path else "dicom_upload"
        dir_id = f"{uuid.uuid4().hex[:12]}_{dirname}"
        dir_path = db.UPLOADS_DIR / dir_id
        dir_path.mkdir(parents=True, exist_ok=True)

        saved_count = 0
        total_size = 0
        for f in files:
            contents = await f.read()
            # Use just the filename (strip any subdirectory from browser path)
            fname = f.filename.split("/")[-1] if f.filename else f"slice_{saved_count}"
            # Skip junk files (keep medical images: DICOM, JPEG, PNG, NIfTI, etc.)
            if fname.startswith('.') or fname.endswith(('.sql', '.txt', '.zip', '.DS_Store')):
                continue
            file_path = dir_path / fname
            with open(file_path, "wb") as out:
                out.write(contents)
            saved_count += 1
            total_size += len(contents)

        if saved_count == 0:
            shutil.rmtree(dir_path, ignore_errors=True)
            raise HTTPException(status_code=400, detail="No valid DICOM files found in upload")

        print(f"Uploaded directory: {dir_path} ({saved_count} files, {total_size} bytes)")
        return {
            "status": "success",
            "dir_path": str(dir_path),
            "dirname": dirname,
            "file_count": saved_count,
            "total_size": total_size,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/available-tools", tags=["agent"], summary="List all discovered MCP tools across all servers")
async def get_available_tools(current_user: dict = Depends(get_current_user)):
    agent = await get_or_create_agent(current_user["user_id"])
    return agent.available_tools

@app.get("/api/enabled-tools", tags=["agent"], summary="List tools currently enabled for the agent")
async def get_enabled_tools(current_user: dict = Depends(get_current_user)):
    agent = await get_or_create_agent(current_user["user_id"])
    return list(agent.agent_tools)

@app.post("/api/enable-tool", tags=["agent"], summary="Enable a specific MCP tool for the agent")
async def enable_tool(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    tool_name = data.get("tool_name")
    if not tool_name:
        return {"error": "tool_name required"}
    uid = current_user["user_id"]
    agent = await get_or_create_agent(uid)
    agent.enable_tool(tool_name)
    db.set_tool_enabled(uid, tool_name, True)
    if data.get("notify", True):
        _push_notification("tool_enabled", f"Tool enabled: {tool_name}")
    return {"status": "enabled", "tool": tool_name}

@app.post("/api/disable-tool", tags=["agent"], summary="Disable a specific MCP tool from the agent")
async def disable_tool(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    tool_name = data.get("tool_name")
    if not tool_name:
        return {"error": "tool_name required"}
    uid = current_user["user_id"]
    agent = await get_or_create_agent(uid)
    agent.disable_tool(tool_name)
    db.set_tool_enabled(uid, tool_name, False)
    if data.get("notify", True):
        _push_notification("tool_disabled", f"Tool disabled: {tool_name}")
    return {"status": "disabled", "tool": tool_name}

@app.post("/api/push-notification", tags=["events"], summary="Push a manual notification to the SSE stream")
async def push_notification(data: dict = Body(...)):
    event_type = data.get("type")
    message = data.get("message")
    if not event_type or not message:
        return {"error": "type and message required"}
    _push_notification(event_type, message)
    return {"status": "ok"}


@app.post("/api/refresh-config", tags=["agent"], summary="Reload mcp-config.json and rediscover available tools")
async def refresh_config(current_user: dict = Depends(get_current_user)):
    agent = await get_or_create_agent(current_user["user_id"])
    await agent.refresh_available_tools()
    return {"status": "refreshed", "available_tools": list(agent.available_tools.keys())}


@app.get("/api/notifications", tags=["agent"], summary="Get MCP event notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    return {"notifications": list(_mcp_notifications)}


@app.post("/api/refresh-server-tools", tags=["agent"], summary="Re-query tools from an already-connected MCP server")
async def refresh_server_tools(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    name = data.get("name")
    if not name:
        return {"error": "name is required"}
    try:
        agent = await get_or_create_agent(current_user["user_id"])
        new_tools = await agent.refresh_server_tools(name)
        return {"status": "refreshed", "server": name, "tools": list(new_tools.keys())}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/add-mcp-server", tags=["agent"], summary="Connect a new MCP server live without restarting")
async def add_mcp_server(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    name = data.get("name")
    cfg = data.get("config")
    if not name or not cfg:
        return {"error": "name and config are required"}
    try:
        agent = await get_or_create_agent(current_user["user_id"])
        new_tools = await agent.add_mcp_server(name, cfg)
        _push_notification("server_added", f"MCP server connected: {name} ({len(new_tools)} tools)")
        for tool in new_tools:
            _push_notification("tool_added", f"New tool available: {tool}")
        return {"status": "connected", "server": name, "tools": list(new_tools.keys())}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/remove-mcp-server", tags=["agent"], summary="Disconnect and remove an MCP server")
async def remove_mcp_server(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    name = data.get("name")
    if not name:
        return {"error": "name is required"}
    try:
        agent = await get_or_create_agent(current_user["user_id"])
        removed_tools = [k for k in agent.available_tools if k.startswith(f"{name}.")]
        await agent.remove_mcp_server(name)
        _push_notification("server_removed", f"MCP server removed: {name}")
        for tool in removed_tools:
            _push_notification("tool_removed", f"Tool removed: {tool}")
        return {"status": "removed", "server": name}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/start-healthcare-conversation", tags=["agent"], summary="Set patient context for the AI agent")
async def start_healthcare_conversation(request: Request, current_user: dict = Depends(get_current_user)):
    try:
        data = await request.json()
        patient_id = data.get("patient_id")
        patient_name = data.get("patient_name")
        if not patient_id or not patient_name:
            return {"error": "patient_id and patient_name are required"}
        agent = await get_or_create_agent(current_user["user_id"])
        agent.set_patient_focus(patient_id, patient_name)
        return {"status": "success", "message": f"Healthcare conversation started for patient {patient_name}", "patient_id": patient_id, "patient_name": patient_name}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/pending-tool", tags=["agent"], summary="Get the tool call awaiting user confirmation (debug mode)")
async def get_pending_tool(current_user: dict = Depends(get_current_user)):
    agent = await get_or_create_agent(current_user["user_id"])
    pending = agent.get_pending_tool()
    if pending:
        return {"pending": True, "tool_name": pending["tool_name"], "arguments": pending["arguments"]}
    return {"pending": False}


def _stream_agent_coro(coro):
    """Wrap an agent coroutine in a keepalive streaming generator.

    Emits ': keepalive' comment lines every 15 s while the coroutine is
    running, then yields the JSON result as the final line.  This prevents
    cloud load-balancers with short idle timeouts from issuing 504s during
    long agentic loops.
    """
    async def _gen():
        try:
            task = asyncio.ensure_future(coro)
            while not task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
            result = task.result()
            yield json.dumps({"result": result}) + "\n"
        except Exception as e:
            yield json.dumps({"result": {"error": str(e)}}) + "\n"

    return StreamingResponse(
        _gen(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"},
    )


@app.post("/api/confirm-tool", tags=["agent"], summary="Confirm and execute the pending tool call")
async def confirm_tool(current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    agent = await get_or_create_agent(uid)
    state = _get_user_state(uid)
    return _stream_agent_coro(agent.confirm_tool_execution(session_id=state.current_session_id))


@app.post("/api/deny-tool", tags=["agent"], summary="Cancel the pending tool call")
async def deny_tool(current_user: dict = Depends(get_current_user)):
    agent = await get_or_create_agent(current_user["user_id"])
    result = agent.deny_tool_execution()
    return {"result": result}



@app.post("/api/clear-files", tags=["files"], summary="Clear the in-memory uploaded file buffer")
async def clear_files(current_user: dict = Depends(get_current_user)):
    state = _get_user_state(current_user["user_id"])
    state.temp_file_paths.clear()
    state.uploaded_files.clear()
    state.uploaded_dirs.clear()
    return {"status": "cleared"}


@app.post("/api/reset-session", tags=["sessions"], summary="Start a fresh session — clears context, LLM history, and uploaded files")
async def reset_session(current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    state.temp_file_paths.clear()
    state.uploaded_files.clear()
    state.uploaded_dirs.clear()
    agent = await get_or_create_agent(uid)
    agent.reset_session_context()
    if agent.llm_client:
        agent.llm_client.start_chat()
    state.current_session_id = db.create_session(user_id=uid)
    return {"status": "session_reset", "session_id": state.current_session_id}


# --- Session Management ---

@app.post("/api/save-session", tags=["sessions"], summary="Persist the current session with a display name")
async def save_session(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    name = data.get("name")
    if not name:
        return {"error": "name is required"}
    if not state.current_session_id:
        return {"error": "No active session"}
    db.update_session(state.current_session_id, name=name, persisted=True)
    agent = await get_or_create_agent(uid)
    agent.save_context_to_db(state.current_session_id)
    return {"status": "saved", "session_id": state.current_session_id, "name": name}


@app.get("/api/sessions", tags=["sessions"], summary="List all sessions (optionally filter to persisted only)")
async def list_sessions(persisted_only: bool = False, current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    sessions = db.list_sessions(persisted_only=persisted_only, user_id=uid)
    for s in sessions:
        files = db.get_session_files(s["id"])
        s["file_count"] = len(files)
        s["total_size"] = db.get_session_total_size(s["id"])
    return {"sessions": sessions, "current_session_id": state.current_session_id}


@app.delete("/api/delete-session", tags=["sessions"], summary="Delete a saved session and its associated files")
async def delete_session(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    session_id = data.get("session_id")
    if not session_id:
        return {"error": "session_id is required"}
    if session_id == state.current_session_id:
        return {"error": "Cannot delete the active session. Switch to another session first."}
    session = db.get_session(session_id)
    if not session or session.get("user_id") != uid:
        return {"error": "Session not found"}
    db.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.delete("/api/delete-all-sessions", tags=["sessions"], summary="Delete all sessions except the currently active one")
async def delete_all_sessions(current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    sessions = db.list_sessions(user_id=uid)
    deleted = []
    for s in sessions:
        if s["id"] != state.current_session_id:
            db.delete_session(s["id"])
            deleted.append(s["id"])
    return {"status": "deleted", "count": len(deleted)}


@app.post("/api/load-session", tags=["sessions"], summary="Load a saved session — restores context and file references")
async def load_session(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    session_id = data.get("session_id")
    if not session_id:
        return {"error": "session_id is required"}

    session = db.get_session(session_id)
    if not session or session.get("user_id") != uid:
        return {"error": "Session not found"}

    state.current_session_id = session_id
    state.uploaded_files.clear()
    state.temp_file_paths.clear()

    session_files_all = db.get_session_files(session_id)
    state.uploaded_dirs.clear()
    for f in session_files_all:
        if f.get("file_type") == "dicom_dir" and os.path.isdir(f["stored_path"]):
            state.uploaded_dirs.append(f["stored_path"])

    agent = await get_or_create_agent(uid)
    agent.load_context_from_db(session_id)

    saved_messages = db.get_messages(session_id)
    if agent.llm_client and saved_messages:
        from google.genai import types as genai_types
        history = []
        for msg in saved_messages:
            role = "user" if msg["role"] == "user" else "model"
            history.append(genai_types.Content(role=role, parts=[genai_types.Part(text=msg["content"])]))
        agent.llm_client.start_chat(history=history)
    elif agent.llm_client:
        agent.llm_client.start_chat()

    if session.get("patient_id") and session.get("patient_name"):
        agent.set_patient_focus(session["patient_id"], session["patient_name"])

    return {
        "status": "loaded",
        "session_id": session_id,
        "name": session["name"],
        "files": db.get_session_files(session_id),
        "messages": saved_messages
    }


@app.get("/api/session-files", tags=["sessions"], summary="Get uploaded files for a session (defaults to current session)")
async def get_session_files(session_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    state = _get_user_state(current_user["user_id"])
    sid = session_id or state.current_session_id
    files = db.get_session_files(sid) if sid else []
    return {"session_id": sid, "files": files}


@app.get("/api/messages", tags=["sessions"], summary="Get conversation messages for a session")
async def get_messages(session_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    state = _get_user_state(current_user["user_id"])
    sid = session_id or state.current_session_id
    messages = db.get_messages(sid) if sid else []
    return {"session_id": sid, "messages": messages}



# --- Test Endpoints: Direct MONAI Tool Calls ---
# These bypass the LLM agent entirely and call MCP tools directly via tool_registry.
# Used by the frontend "Test" tab for manually stepping through the inference pipeline
# (select file -> analyze -> pick model -> download -> run inference).

@app.get("/api/monai/sample-data", tags=["monai"], summary="List available sample/test medical image files and DICOM series directories")
async def list_sample_data(current_user: dict = Depends(get_current_user)):
    """List available sample data files for testing"""
    base = Path(__file__).parent.parent
    # Scan known sample/test directories for medical image files
    scan_dirs = [
        (base / "mcp-monai" / "sample_data" / "Task09_Spleen" / "Task09_Spleen" / "imagesTr", "spleen_dataset"),
        (base / "test_data", "test_data"),
    ]

    files = []
    for scan_dir, source_label in scan_dirs:
        if not scan_dir.exists():
            continue
        for f in sorted(scan_dir.iterdir()):
            if not f.is_file() or f.name.startswith('.'):
                continue
            if f.suffix == '.dcm':
                ftype = "dcm"
            elif f.name.endswith('.nii.gz'):
                ftype = "nii.gz"
            elif f.suffix == '.nii':
                ftype = "nii"
            else:
                continue
            files.append({
                "name": f.name,
                "path": str(f.resolve()),
                "size": f.stat().st_size,
                "type": ftype,
                "source": source_label,
            })

    # Scan for DICOM series directories (folders of 2D slices)
    def _is_dicom_series(d: Path) -> int:
        """Returns slice count if dir looks like a DICOM series, 0 otherwise."""
        if not d.is_dir():
            return 0
        count = 0
        for child in d.iterdir():
            if child.is_file() and not child.name.startswith('.'):
                if child.suffix == '.dcm' or not child.suffix:
                    count += 1
        return count

    dicom_root = base / "test_data" / "DICOM"
    if dicom_root.exists():
        for study_dir in sorted(dicom_root.iterdir()):
            if not study_dir.is_dir() or study_dir.name.startswith('.'):
                continue
            for series_dir in sorted(study_dir.iterdir()):
                slice_count = _is_dicom_series(series_dir)
                if slice_count == 0:
                    continue
                total_size = sum(
                    f.stat().st_size for f in series_dir.iterdir()
                    if f.is_file() and not f.name.startswith('.')
                )
                files.append({
                    "name": f"{series_dir.name} ({slice_count} slices)",
                    "path": str(series_dir.resolve()),
                    "size": total_size,
                    "type": "dicom_series",
                    "source": "dicom_series",
                })

    # Also check uploaded directories in UPLOADS_DIR
    if db.UPLOADS_DIR.exists():
        for d in sorted(db.UPLOADS_DIR.iterdir()):
            if d.is_dir():
                dir_files = [f for f in d.iterdir() if f.is_file() and not f.name.startswith('.')]
                if not dir_files:
                    continue
                total_size = sum(f.stat().st_size for f in dir_files)
                # Detect type from file extensions
                sample_ext = dir_files[0].suffix.lower()
                if sample_ext in ('.jpg', '.jpeg', '.png'):
                    dir_type = "image_series"
                else:
                    dir_type = "dicom_series"
                files.append({
                    "name": f"{d.name} ({len(dir_files)} files)",
                    "path": str(d.resolve()),
                    "size": total_size,
                    "type": dir_type,
                    "source": "uploaded",
                })

    # Also include single files uploaded to the DB
    conn = db._get_conn()
    rows = conn.execute(
        "SELECT original_name, stored_path, file_type, file_size FROM uploaded_files ORDER BY uploaded_at DESC"
    ).fetchall()
    conn.close()
    for row in rows:
        path = row["stored_path"]
        if os.path.exists(path):
            files.append({
                "name": row["original_name"],
                "path": path,
                "size": row["file_size"] or 0,
                "type": row["file_type"] or "unknown",
                "source": "uploaded",
            })

    return {"files": files}


@app.post("/api/monai/validate-series", tags=["monai"], summary="Validate a DICOM series directory — returns series metadata and warnings")
async def validate_series(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Validate a DICOM series directory using utils.parse_dicom_directory"""
    dir_path = data.get("path")
    if not dir_path or not os.path.isdir(dir_path):
        raise HTTPException(status_code=400, detail="Valid directory path is required")

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif'}
    dir_files = [f for f in Path(dir_path).iterdir() if f.is_file() and not f.name.startswith('.')]
    if dir_files and Path(dir_files[0].name).suffix.lower() in IMAGE_EXTS:
        return {
            "valid": True,
            "is_image_dir": True,
            "total_files": len(dir_files),
            "series_count": 1,
            "series": [{
                "uid": "image_dir",
                "modality": None,
                "body_part": None,
                "description": f"Image slice directory ({len(dir_files)} slices)",
                "slice_count": len(dir_files),
                "files": [str(f) for f in dir_files[:5]],
            }],
            "warnings": [],
        }

    try:
        agent = await get_or_create_agent(current_user["user_id"])
        result = await agent.tool_registry.execute_tool(
            "utils.parse_dicom_directory", {"dir_path": dir_path}, logs=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {e}")

    if result.get("error") or result.get("is_error"):
        return {"valid": False, "error": result.get("error", "Unknown error"), "warnings": []}

    total_files = result.get("total_files", 0)
    raw_series = result.get("series", {})
    warnings = []

    if total_files == 0:
        return {"valid": False, "error": "No valid DICOM files found in directory", "warnings": []}

    if len(raw_series) > 1:
        warnings.append(f"Multiple series found ({len(raw_series)}). Select one to proceed.")

    series_list = []
    for uid, info in raw_series.items():
        series_list.append({
            "uid": uid,
            "modality": info.get("modality"),
            "body_part": info.get("body_part"),
            "description": info.get("series_description"),
            "slice_count": info.get("num_slices", len(info.get("files", []))),
            "files": info.get("files", []),
        })

    return {
        "valid": True,
        "total_files": total_files,
        "series_count": len(series_list),
        "series": series_list,
        "warnings": warnings,
    }


@app.post("/api/monai/analyze", tags=["monai"], summary="Analyze a medical image — returns modality, shape, body part, and compatible models")
async def monai_analyze(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    path = data.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    agent = await get_or_create_agent(current_user["user_id"])
    result = await agent.tool_registry.execute_tool(
        "monai.analyze_image", {"image_path": path}, logs=True
    )
    return result


@app.post("/api/monai/list-models", tags=["monai"], summary="List available MONAI model bundles (filterable by category, modality, body part)")
async def monai_list_models(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    args = {}
    if data.get("category"):
        args["category"] = data["category"]
    if data.get("modality"):
        args["modality"] = data["modality"]
    if data.get("body_part"):
        args["body_part"] = data["body_part"]
    agent = await get_or_create_agent(current_user["user_id"])
    result = await agent.tool_registry.execute_tool("monai.list_models", args, logs=True)
    return result


@app.post("/api/monai/download-model", tags=["monai"], summary="Download a MONAI Model Zoo bundle by name")
async def monai_download_model(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    model_name = data.get("model_name")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")
    agent = await get_or_create_agent(current_user["user_id"])
    result = await agent.tool_registry.execute_tool(
        "monai.download_model", {"model_name": model_name}, logs=True
    )
    return result


@app.post("/api/monai/run-inference", tags=["monai"], summary="Run MONAI inference on a medical image with a specified model")
async def monai_run_inference(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    image_path = data.get("image_path")
    model_name = data.get("model_name")
    if not image_path or not model_name:
        raise HTTPException(status_code=400, detail="image_path and model_name required")
    agent = await get_or_create_agent(current_user["user_id"])
    result = await agent.tool_registry.execute_tool(
        "monai.run_inference",
        {"image_path": image_path, "model_name": model_name},
        logs=True
    )
    return result


@app.get("/api/patients", tags=["system"], summary="Get patient list from FHIR server (falls back to mock data if unavailable)")
async def get_patients(current_user: dict = Depends(get_current_user)):
    """Get list of patients from FHIR server"""
    try:
        # Call FHIR MCP server directly
        import requests
        
        mcp_server_url = "http://localhost:8000"
        
        # Call the search tool directly
        response = requests.post(
            f"{mcp_server_url}/mcp/tools/call",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {
                        "type": "Patient",
                        "searchParam": {"_count": "10"}
                    }
                },
                "id": 1
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"MCP response: {result}")
            
            # MCP wraps result in content[0].text as JSON string
            mcp_result = result.get("result", {})
            content = mcp_result.get("content", [])
            
            if content and len(content) > 0:
                text = content[0].get("text", "")
                if text:
                    bundle_data = json.loads(text)
                    
                    # Extract patients from FHIR Bundle
                    patients = []
                    if bundle_data.get("resourceType") == "Bundle" and "entry" in bundle_data:
                        for entry in bundle_data["entry"]:
                            resource = entry.get("resource", {})
                            if resource.get("resourceType") == "Patient":
                                patients.append(format_patient(resource))
                    
                    print(f"Found {len(patients)} patients")
                    return {"patients": patients}
        
        print(f"MCP call failed with status {response.status_code}: {response.text}")
        # Fallback to mock data
        return {"patients": get_mock_patients()}
        
    except Exception as e:
        print(f"Error fetching patients: {e}")
        # Return mock data as fallback
        return {"patients": get_mock_patients()}

def format_patient(patient_resource):
    """Format FHIR Patient resource for frontend display"""
    try:
        patient_id = patient_resource.get("id", "Unknown")
        
        # Extract name
        names = patient_resource.get("name", [])
        full_name = "Unknown Name"
        if names:
            name = names[0]
            given = name.get("given", [])
            family = name.get("family", "")
            full_name = f"{' '.join(given)} {family}".strip()
        
        # Extract other info
        birth_date = patient_resource.get("birthDate", "Unknown")
        gender = patient_resource.get("gender", "Unknown").capitalize()
        
        return {
            "id": patient_id,
            "name": full_name,
            "birthDate": birth_date,
            "gender": gender,
            "resource": patient_resource  # Keep full resource for context
        }
    except Exception as e:
        print(f"Error formatting patient: {e}")
        return {
            "id": "Unknown",
            "name": "Error loading patient",
            "birthDate": "Unknown",
            "gender": "Unknown",
            "resource": patient_resource
        }

def get_mock_patients():
    """Fallback mock patient data"""
    return [
        {
            "id": "patient-001",
            "name": "John Smith",
            "birthDate": "1985-03-15",
            "gender": "Male",
            "resource": {
                "id": "patient-001",
                "resourceType": "Patient",
                "name": [{"given": ["John"], "family": "Smith"}],
                "birthDate": "1985-03-15",
                "gender": "male"
            }
        },
        {
            "id": "patient-002",
            "name": "Sarah Johnson",
            "birthDate": "1992-07-22",
            "gender": "Female",
            "resource": {
                "id": "patient-002",
                "resourceType": "Patient",
                "name": [{"given": ["Sarah"], "family": "Johnson"}],
                "birthDate": "1992-07-22",
                "gender": "female"
            }
        }
    ]


# --- Background Tasks & SSE ---

@app.get("/api/events", tags=["events"], summary="SSE stream — emits task_queued, task_running, task_done, task_failed events")
async def sse_events(request: Request, token: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    """
    Server-Sent Events endpoint.  Polls the DB every second and emits an event
    the first time a task reaches 'done' or 'failed'.

    We only add a task to `notified` AFTER the yield succeeds so that a failed
    yield (connection drop mid-send) doesn't permanently suppress the event.
    """
    async def event_generator():
        # Top-level guard: any BaseException (CancelledError, GeneratorExit, etc.)
        # thrown into a yield point causes a clean return so starlette's task group
        # never sees an unhandled error from this generator.
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"

            # Pre-populate so we don't replay old done/failed notifications on reconnect.
            # Only mark done/failed tasks as already-notified — queued/running tasks are
            # re-emitted so the client never misses a notification due to SSE reconnects.
            notified: set = set()   # tasks already sent done/failed event
            started: set = set()    # tasks already sent running event
            seen_ids: set = set()   # all task IDs ever seen (to detect brand-new tasks)
            try:
                for t in db.list_tasks(user_id=current_user["user_id"]):
                    if t["status"] in ("done", "failed", "cancelled"):
                        seen_ids.add(t["id"])
                        notified.add(t["id"])
                        started.add(t["id"])
                    # queued/running tasks are intentionally NOT added to seen_ids
                    # so they get task_queued / task_running re-emitted after reconnect
            except Exception as e:
                print(f"[SSE] init error: {e}")

            keepalive_ticks = 0
            notified_mcp: set = set()  # indices of already-sent MCP notifications
            notified_console: int = 0  # index into watcher_service console log

            while True:
                # Sleep 1s, but wake up immediately if the server is shutting down
                try:
                    if _shutdown_event is not None:
                        await asyncio.wait_for(_shutdown_event.wait(), timeout=1.0)
                        return  # Server shutting down - exit generator cleanly
                    else:
                        await asyncio.sleep(1.0)
                except asyncio.TimeoutError:
                    pass  # Normal 1-second tick
                except asyncio.CancelledError:
                    return  # HTTP task was cancelled

                if await request.is_disconnected():
                    break

                # Emit new MCP notifications
                for i, notif in enumerate(_mcp_notifications):
                    if i not in notified_mcp:
                        notified_mcp.add(i)
                        yield f"data: {json.dumps({'type': 'mcp_notification', **notif})}\n\n"

                # Emit new directory console lines
                console_log = watcher_service.get_console_log()
                for entry in console_log[notified_console:]:
                    notified_console += 1
                    yield f"data: {json.dumps({'type': 'directory_console', **entry})}\n\n"

                try:
                    tasks = db.list_tasks(user_id=current_user["user_id"])
                except Exception as e:
                    print(f"[SSE] db.list_tasks error: {e}")
                    continue

                for task in tasks:
                    tid = task["id"]
                    status = task["status"]

                    # Emit task_queued the first time a brand-new task appears
                    if tid not in seen_ids:
                        seen_ids.add(tid)
                        payload = {
                            "type": "task_queued",
                            "task_id": tid,
                            "task_type": task["task_type"],
                            "description": task["description"],
                            "session_id": task["session_id"],
                        }
                        print(f"[SSE] emitting task_queued for {tid[:8]}")
                        yield f"data: {json.dumps(payload)}\n\n"

                    # Emit task_running the first time a task enters running state
                    if status == "running" and tid not in started:
                        payload = {
                            "type": "task_running",
                            "task_id": tid,
                            "task_type": task["task_type"],
                            "description": task["description"],
                            "session_id": task["session_id"],
                        }
                        print(f"[SSE] emitting task_running for {tid[:8]}")
                        yield f"data: {json.dumps(payload)}\n\n"
                        started.add(tid)

                    if tid in notified or status not in ("done", "failed", "cancelled"):
                        continue

                    event_type = "task_done" if status == "done" else ("task_cancelled" if status == "cancelled" else "task_failed")
                    payload = {
                        "type": event_type,
                        "task_id": tid,
                        "task_type": task["task_type"],
                        "description": task["description"],
                        "session_id": task["session_id"],
                    }
                    if status == "failed":
                        payload["error"] = task.get("error", "")

                    print(f"[SSE] emitting {event_type} for {tid[:8]}")
                    yield f"data: {json.dumps(payload)}\n\n"
                    # Only mark notified AFTER the yield succeeds
                    notified.add(tid)

                keepalive_ticks += 1
                if keepalive_ticks >= 15:
                    yield ": keepalive\n\n"
                    keepalive_ticks = 0

        except (GeneratorExit, asyncio.CancelledError):
            return  # Client disconnected — clean exit
        except BaseException as _sse_err:
            print(f"[SSE] generator closed unexpectedly: {type(_sse_err).__name__}: {_sse_err}")
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/tasks", tags=["events"], summary="List background inference/report tasks, optionally filtered by session")
async def list_tasks(session_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    tasks = db.list_tasks(session_id=session_id, user_id=current_user["user_id"])
    return {"tasks": tasks}


@app.post("/api/tasks/{task_id}/cancel", tags=["events"], summary="Cancel a queued or running background task")
async def cancel_task(task_id: str, current_user: dict = Depends(get_current_user)):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] not in ("queued", "running"):
        raise HTTPException(status_code=400, detail=f"Task is already {task['status']}")
    task_runner.cancel_task(task_id)
    return {"status": "cancelled", "task_id": task_id}


@app.get("/api/files/image", tags=["files"], summary="Serve an image file by absolute path (uploads and workspaces only)")
async def serve_image(path: str, current_user: dict = Depends(get_current_user)):
    """Serve an image from the uploads or workspaces directory for display in the UI."""
    abs_path = os.path.realpath(path)
    allowed_roots = [
        os.path.realpath(str(db.UPLOADS_DIR)),
        os.path.realpath(WORKSPACES_ROOT),
    ]
    if not any(abs_path.startswith(root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="Access to this path is not allowed")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(abs_path)


@app.post("/api/generate-report", tags=["events"], summary="Queue a radiology report generation task from selected inference results")
async def generate_report(data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    uid = current_user["user_id"]
    state = _get_user_state(uid)
    if not state.current_session_id:
        state.current_session_id = db.create_session(user_id=uid)
    task_ids = data.get("task_ids", [])
    if not task_ids:
        raise HTTPException(status_code=400, detail="task_ids is required")

    patient_context = data.get("patient_context", {})
    description = f"Report from {len(task_ids)} inference result(s)"

    task_id = task_runner.submit_task(
        session_id=state.current_session_id,
        task_type="report",
        description=description,
        input_data={"task_ids": task_ids, "patient_context": patient_context},
    )

    return {"status": "queued", "task_id": task_id, "description": description}


@app.get("/api/health", tags=["system"], summary="Health check")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/system-stats", tags=["system"], summary="RAM, disk and CPU usage")
async def system_stats():
    import psutil
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/app")
    all_dirs = db.list_watched_directories_all()
    watched_active = sum(1 for d in all_dirs if watcher_service.is_watching(d["id"]))
    executor = task_runner._executor
    queue_size = executor._work_queue.qsize() if hasattr(executor, "_work_queue") else None
    active_threads = len([t for t in executor._threads if t.is_alive()]) if hasattr(executor, "_threads") else None
    return {
        "ram": {
            "total_gb": round(vm.total / 1e9, 2),
            "used_gb": round(vm.used / 1e9, 2),
            "available_gb": round(vm.available / 1e9, 2),
            "percent": vm.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1e9, 2),
            "used_gb": round(disk.used / 1e9, 2),
            "free_gb": round(disk.free / 1e9, 2),
            "percent": disk.percent,
        },
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "watched_dirs": {"total": len(all_dirs), "active": watched_active},
        "task_queue": {"active_threads": active_threads, "queued": queue_size, "max_workers": task_runner._MAX_WORKERS},
    }


@app.get("/api/diagnostics", tags=["system"], summary="Run server-side diagnostics")
async def run_diagnostics():
    """Check MONAI venv, model bundles, and system state. Useful when you can't SSH in."""
    import subprocess
    import platform
    import sys
    from pathlib import Path as _P

    app_root = _P(os.environ.get("APP_ROOT", "/app"))
    monai_python = str(app_root / "mcp-monai" / "venv" / "bin" / "python")
    results = {}

    # Python + package versions inside the MONAI venv
    try:
        out = subprocess.run(
            [monai_python, "-c",
             "import sys, torch, monai, mcp; "
             "print(f'python {sys.version}'); "
             "print(f'torch {torch.__version__}'); "
             "print(f'monai {monai.__version__}'); "
             "print(f'mcp {getattr(mcp, \"__version__\", \"(no __version__)\")}')"
             ],
            capture_output=True, text=True, timeout=30
        )
        results["monai_venv"] = {
            "ok": out.returncode == 0,
            "output": (out.stdout + out.stderr).strip()
        }
    except Exception as e:
        results["monai_venv"] = {"ok": False, "output": str(e)}

    # Model bundles
    bundles_root = app_root / "mcp-monai" / "bundles"
    bundle_info = {}
    if bundles_root.exists():
        for d in sorted(bundles_root.iterdir()):
            if not d.is_dir():
                continue
            models_dir = d / "models"
            if not models_dir.exists():
                bundle_info[d.name] = {"status": "missing models/ dir"}
                continue
            pt_files = list(models_dir.glob("*.pt")) + list(models_dir.glob("*.ts"))
            if not pt_files:
                bundle_info[d.name] = {"status": "no weight files"}
            else:
                bundle_info[d.name] = {
                    "status": "ok",
                    "files": {f.name: f"{f.stat().st_size / 1e6:.0f} MB" for f in pt_files}
                }
    else:
        bundle_info["__error__"] = "bundles directory not found"
    results["bundles"] = bundle_info

    # Last MONAI inference stderr (crash output from subprocess)
    stderr_log = app_root / "orchestrator" / "data" / "monai_inference_stderr.log"
    if stderr_log.exists():
        try:
            text = stderr_log.read_text(errors="replace")
            results["monai_stderr"] = text[-4000:] if len(text) > 4000 else text
        except Exception as e:
            results["monai_stderr"] = f"error reading log: {e}"
    else:
        results["monai_stderr"] = None

    # Last Cellpose stderr (crash output from subprocess)
    cellpose_log = app_root / "orchestrator" / "data" / "cellpose_stderr.log"
    if cellpose_log.exists():
        try:
            text = cellpose_log.read_text(errors="replace")
            results["cellpose_stderr"] = text[-16000:] if len(text) > 16000 else text
        except Exception as e:
            results["cellpose_stderr"] = f"error reading log: {e}"
    else:
        results["cellpose_stderr"] = None

    # Uploads directory
    uploads = app_root / "orchestrator" / "data" / "uploads"
    try:
        n = len(list(uploads.iterdir())) if uploads.exists() else 0
        results["uploads"] = {"exists": uploads.exists(), "file_count": n}
    except Exception as e:
        results["uploads"] = {"exists": False, "error": str(e)}

    # System
    try:
        import psutil
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(str(app_root))
        results["system"] = {
            "platform": platform.platform(),
            "python": sys.version,
            "ram_available_gb": round(vm.available / 1e9, 1),
            "ram_total_gb": round(vm.total / 1e9, 1),
            "disk_free_gb": round(disk.free / 1e9, 1),
            "disk_total_gb": round(disk.total / 1e9, 1),
        }
    except Exception as e:
        results["system"] = {"error": str(e)}

    return results


if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:5001")
    uvicorn.run(app, host="0.0.0.0", port=5001, timeout_graceful_shutdown=3)

