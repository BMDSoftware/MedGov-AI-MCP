#!/usr/bin/env python3
import asyncio
import json
import os
import shutil
import uuid
from typing import Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Load env BEFORE importing agenticAgent so LLM_BACKEND is set
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from agenticAgent import agent_decision
import database as db
import task_runner
from watcher_service import watcher_service

current_session_id: Optional[str] = None
_shutdown_event: Optional[asyncio.Event] = None
_mcp_notifications: list = []  # in-memory MCP event log


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


async def _poll_mcp_tools(interval: int = 30):
    """Periodically re-query all connected MCP servers for tool changes."""
    while True:
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=interval)
            return  # shutdown signalled
        except asyncio.TimeoutError:
            pass
        try:
            servers = list(agent_decision.tool_registry.sessions.keys())
            for name in servers:
                try:
                    old_keys = set(k for k in agent_decision.available_tools if k.startswith(f"{name}."))
                    new_tools = await agent_decision.tool_registry.refresh_server_tools(name)
                    new_keys = set(new_tools.keys())
                    added = new_keys - old_keys
                    removed = old_keys - new_keys
                    for k in old_keys:
                        agent_decision.available_tools.pop(k, None)
                        agent_decision.agent_tools.discard(k)
                    agent_decision.available_tools.update(new_tools)
                    agent_decision.agent_tools.update(new_keys)
                    for k in added:
                        _push_notification("tool_added", f"New tool available: {k}")
                    for k in removed:
                        _push_notification("tool_removed", f"Tool removed: {k}")
                except Exception:
                    pass
            agent_decision._refresh_agent_components()
        except Exception:
            pass


async def _watcher_execute(dir_id: str, files: list):
    """Called by watcher_service when new files are detected in a watched directory."""
    wd = db.get_watched_directory(dir_id)
    if not wd or not wd["enabled"]:
        return

    file_list = "\n".join(f"  - {f}" for f in files)
    custom = (wd.get("custom_prompt") or "").strip()

    if custom:
        # Custom prompt is the full job description — don't layer medical analysis on top
        goal = (
            f"New file(s) detected in watched directory '{wd['name']}' (path: {wd['path']}).\n\n"
            f"Files detected:\n{file_list}\n\n"
            f"{custom}"
        )
    else:
        # Default: classify and organize only. Do NOT run analysis or inference automatically.
        # Inference should only happen when the user explicitly asks for it via a custom prompt.
        goal = (
            f"New file(s) detected in watched directory '{wd['name']}' (path: {wd['path']}).\n\n"
            f"Files detected:\n{file_list}\n\n"
            "Your job is to CLASSIFY and ORGANIZE these files only. Do NOT run analysis or inference unless explicitly instructed.\n\n"
            "Steps:\n"
            "1. Check if each file is a DICOM, NIfTI, or other medical imaging format using the available parse tools.\n"
            "2. Based on the file type, move it to an appropriate subdirectory:\n"
            "   - DICOM → 'dicom/'\n"
            "   - NIfTI (.nii, .nii.gz) → 'nifti/'\n"
            "   - Unknown or unreadable → 'uncertain/'\n"
            "3. Write a brief one-line note alongside each file if helpful.\n"
            "Do NOT call analyze_image or run_inference. Classification and organization is the only goal."
        )
    watcher_service.push_console(dir_id, "[AI] Starting autonomous analysis...")
    agent_decision.set_agent_type(True)
    original_require_confirmation = agent_decision.require_confirmation
    agent_decision.require_confirmation = False
    allowed_tools = wd.get("allowed_tools")  # None = all tools, list = restricted set
    original_agent_tools = None
    if allowed_tools is not None:
        original_agent_tools = set(agent_decision.agent_tools)
        agent_decision.agent_tools = original_agent_tools & set(allowed_tools)
        agent_decision._refresh_agent_components()
    try:
        image_list = [(f, b"") for f in files]
        result = await agent_decision.execute_task(goal, fileList=image_list, session_id=current_session_id)
    finally:
        agent_decision.set_agent_type(False)
        agent_decision.require_confirmation = original_require_confirmation
        if original_agent_tools is not None:
            agent_decision.agent_tools = original_agent_tools
            agent_decision._refresh_agent_components()
    if result and result.get("answer"):
        watcher_service.push_console(dir_id, f"[AI] {result['answer']}")
    watcher_service.push_console(dir_id, "[AI] Analysis complete.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global current_session_id, _shutdown_event
    _shutdown_event = asyncio.Event()
    # Startup
    db.init_db()
    current_session_id = db.create_session()
    await agent_decision._initialize_components()
    agent_decision.set_mode(_app_settings.get("mode", "debug"))
    task_runner.init()
    asyncio.create_task(_poll_mcp_tools(30))

    # Start watcher service and resume all enabled watched directories
    watcher_service.set_execute_callback(_watcher_execute)
    await watcher_service.start()
    for wd in db.list_watched_directories():
        if wd["enabled"]:
            watcher_service.start_watching(wd["id"], wd["path"], wd["name"])
    try:
        yield
    except asyncio.CancelledError:
        # uvicorn cancels the lifespan task on shutdown. Uncancel so that
        # cleanup awaits below can run without immediately re-raising, and
        # so that @asynccontextmanager sees the generator exit normally
        # (causing starlette to send shutdown.complete, not shutdown.failed).
        task = asyncio.current_task()
        if task is not None:
            task.uncancel()
    finally:
        # Signal SSE connections to exit cleanly before MCP sessions close
        _shutdown_event.set()
        await watcher_service.stop()
        # Shutdown - close MCP sessions
        agent_decision.reset_session_context()
        try:
            await agent_decision.close()
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploaded_files = []  # In-memory buffer for uploaded files (appended, not replaced)
temp_file_paths = {}  # Temp file paths mapped by filename
uploaded_dirs: List[str] = []  # Directory paths registered for the current session


image_metadata = {"modality": None, "bodyPart": None}

@app.post("/api/set-metadata", tags=["files"], summary="Set image modality and body part metadata")
async def set_metadata(data: dict = Body(...)):
    global image_metadata
    image_metadata["modality"] = data.get("modality")
    image_metadata["bodyPart"] = data.get("bodyPart")
    return {"status": "ok"}


@app.get("/api/mode", tags=["system"], summary="Get current UI mode (debug or normal)")
async def get_mode():
    return {"mode": _app_settings.get("mode", "debug")}

@app.post("/api/mode", tags=["system"], summary="Set UI mode — 'debug' shows tool calls, 'normal' uses clinical language")
async def set_mode(data: dict = Body(...)):
    mode = data.get("mode", "debug")
    if mode not in ("debug", "normal"):
        raise HTTPException(status_code=400, detail="mode must be 'debug' or 'normal'")
    _app_settings["mode"] = mode
    _save_settings(_app_settings)
    agent_decision.set_mode(mode)
    return {"mode": mode}


# --- Watched Directories ---

@app.get("/api/watched-directories", tags=["system"], summary="List all watched directories")
async def list_watched_directories():
    dirs = db.list_watched_directories()
    for d in dirs:
        d["watching"] = watcher_service.is_watching(d["id"])
    return dirs


@app.post("/api/watched-directories", tags=["system"], summary="Add a new watched directory")
async def create_watched_directory(data: dict = Body(...)):
    name = data.get("name", "").strip()
    path = data.get("path", "").strip()
    custom_prompt = (data.get("custom_prompt") or "").strip() or None
    allowed_tools = data.get("allowed_tools") or None
    if not name or not path:
        raise HTTPException(status_code=400, detail="name and path are required")
    dir_id = db.create_watched_directory(name, path, custom_prompt, allowed_tools)
    watcher_service.push_console(dir_id, f"[INFO] Directory '{name}' added.")
    wd = db.get_watched_directory(dir_id)
    watcher_service.start_watching(dir_id, wd["path"], wd["name"])
    wd["watching"] = watcher_service.is_watching(dir_id)
    return wd


@app.put("/api/watched-directories/{dir_id}", tags=["system"], summary="Update a watched directory")
async def update_watched_directory(dir_id: str, data: dict = Body(...)):
    wd = db.get_watched_directory(dir_id)
    if not wd:
        raise HTTPException(status_code=404, detail="Not found")
    was_watching = watcher_service.is_watching(dir_id)
    allowed_tools = data.get("allowed_tools")
    db.update_watched_directory(
        dir_id,
        name=data.get("name"),
        path=data.get("path"),
        custom_prompt=data.get("custom_prompt"),
        enabled=data.get("enabled"),
        allowed_tools=allowed_tools if allowed_tools else None,
        clear_allowed_tools=("allowed_tools" in data and not allowed_tools)
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
async def delete_watched_directory(dir_id: str):
    wd = db.get_watched_directory(dir_id)
    if not wd:
        raise HTTPException(status_code=404, detail="Not found")
    watcher_service.stop_watching(dir_id)
    db.delete_watched_directory(dir_id)
    return {"status": "deleted"}


@app.get("/api/watched-directories/{dir_id}/console", tags=["system"], summary="Get console log for a watched directory")
async def get_directory_console(dir_id: str):
    return watcher_service.get_console_log(dir_id)


@app.get("/api/browse-directory", tags=["system"], summary="Browse filesystem directories for the directory picker")
async def browse_directory(path: str = "/"):
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


@app.post("/api/set-directory", tags=["files"], summary="Add, remove, or clear registered DICOM series directories")
async def set_directory(data: dict = Body(...)):
    """
    Manage the list of registered directories for the current session.
      { dir_path: "/path" }            → add directory
      { dir_path: "/path", remove: true } → remove that specific directory
      { dir_path: null }               → clear all directories
    """
    dir_path = data.get("dir_path")
    remove = data.get("remove", False)

    if dir_path is None:
        # Clear all
        uploaded_dirs.clear()
        db.remove_session_dirs(current_session_id)
    elif remove:
        # Remove specific directory
        if dir_path in uploaded_dirs:
            uploaded_dirs.remove(dir_path)
        db.remove_session_dir(current_session_id, dir_path)
    else:
        # Add directory if valid and not already in list
        if os.path.isdir(dir_path) and dir_path not in uploaded_dirs:
            uploaded_dirs.append(dir_path)
            dirname = Path(dir_path).name
            total_size = sum(f.stat().st_size for f in Path(dir_path).iterdir() if f.is_file())
            db.save_uploaded_file(current_session_id, dirname, dir_path, 'dicom_dir', total_size)

    return {"status": "ok", "dirs": uploaded_dirs}


@app.get("/api/available-models", tags=["agent"], summary="List available Gemini models for the configured API key")
async def available_models():
    try:
        from google import genai as google_genai
        client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        models = [m.name.replace("models/", "") for m in client.models.list() if "generateContent" in (m.supported_actions or [])]
        return {"models": sorted(models)}
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.post("/api/set-model", tags=["agent"], summary="Switch the LLM model for the current session")
async def set_model(data: dict = Body(...)):
    model_id = data.get("model_id")
    if not model_id:
        return {"error": "model_id is required"}
    if agent_decision.llm_client:
        agent_decision.llm_client.set_model(model_id)
    return {"status": "ok", "model_id": model_id}


@app.get("/api/current-model", tags=["agent"], summary="Get the currently active LLM model")
async def get_current_model():
    model_id = agent_decision.llm_client.model_id if agent_decision.llm_client else os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return {"model_id": model_id}


@app.post("/api/change-agent-type", tags=["agent"], summary="Switch between default and autonomous agent modes")
async def change_agent_type(data: str = Body(...)):
    if data == "autonomous":
        autonomous = True
    else:
        autonomous = False
    agent_decision.set_agent_type(autonomous=autonomous)
    return {"status": "ok", "agent_type": "autonomous" if autonomous else "default"}


@app.post("/api/process-query", tags=["agent"], summary="Send a natural language query to the AI agent")
async def process_query(query: str = Body(..., media_type="text/plain")):
    print(f"Processing ad-hoc query: {query}")
    try:
        # Get files for current session from DB (persistent paths)
        session_files = db.get_session_files(current_session_id)

        if not uploaded_files and not session_files and not uploaded_dirs:
            result = await agent_decision.execute_task(query, session_id=current_session_id)
        else:
            image_data = []
            # Use in-memory files first (just uploaded), fall back to DB files
            if uploaded_files:
                for filename, contents in uploaded_files:
                    stored_path = temp_file_paths.get(filename)
                    if stored_path and os.path.exists(stored_path):
                        image_data.append((stored_path, contents))
                        print(f"Using persistent file: {stored_path}")
            elif session_files:
                # Load from persistent storage (skip dicom_dir entries - handled separately)
                for f in session_files:
                    if f.get("file_type") == "dicom_dir":
                        continue
                    path = f["stored_path"]
                    if os.path.exists(path):
                        with open(path, "rb") as fh:
                            contents = fh.read()
                        image_data.append((path, contents))
                        print(f"Using DB file: {path}")

            # Include all registered directories
            for dir_path in uploaded_dirs:
                if os.path.isdir(dir_path):
                    image_data.append((dir_path, b""))
                    print(f"Using uploaded directory: {dir_path}")

            # If no in-memory files, fall back to session dirs from DB
            if not image_data or all(p == b"" for _, p in image_data):
                session_dirs = [f for f in session_files if f.get("file_type") == "dicom_dir"]
                for f in session_dirs:
                    if os.path.isdir(f["stored_path"]) and f["stored_path"] not in uploaded_dirs:
                        image_data.append((f["stored_path"], b""))
                        print(f"Using DB directory: {f['stored_path']}")

            if image_data:
                result = await agent_decision.execute_task(query, fileList=image_data, session_id=current_session_id)
            else:
                result = await agent_decision.execute_task(query, session_id=current_session_id)

        db.save_message(current_session_id, "user", query)
        if isinstance(result, dict):
            agent_text = result.get("answer") or result.get("response") or result.get("error") or ""
        else:
            agent_text = str(result)
        if agent_text:
            db.save_message(current_session_id, "assistant", agent_text)
        return {"result": result}
    except Exception as e:
        print(f"Error processing query: {e}")
        return {"result": {"error": str(e)}}



@app.post("/api/upload", tags=["files"], summary="Upload a single medical image file (.dcm, .nii.gz, etc.)")
async def upload_file(file: UploadFile = File(...)):
    global uploaded_files, temp_file_paths
    print(f"Received file: {file.filename}")
    try:
        contents = await file.read()

        # Persist to data/uploads/ with unique name
        ext = os.path.splitext(file.filename)[1] if not file.filename.endswith('.nii.gz') else '.nii.gz'
        stored_name = f"{uuid.uuid4().hex[:12]}_{file.filename}"
        stored_path = str(db.UPLOADS_DIR / stored_name)

        with open(stored_path, "wb") as f:
            f.write(contents)

        # Track in database
        file_type = ext.lstrip('.') or 'unknown'
        file_id = db.save_uploaded_file(current_session_id, file.filename, stored_path, file_type, len(contents))

        # Keep in memory for immediate query use
        uploaded_files.append((file.filename, contents))
        temp_file_paths[file.filename] = stored_path

        print(f"Uploaded {file.filename} -> {stored_path} (file_id={file_id})")
        return {"status": "success", "filename": file.filename, "size": len(contents), "file_id": file_id, "stored_path": stored_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/upload", tags=["files"], summary="Remove an uploaded file from the session")
async def remove_file(filename: str):
    global uploaded_files, temp_file_paths
    print(f"Removing file: {filename}")
    for i, (fname, _) in enumerate(uploaded_files):
        if fname == filename:
            del uploaded_files[i]
            # Remove corresponding temp file if exists
            if filename in temp_file_paths:
                try:
                    os.unlink(temp_file_paths[filename])
                except Exception:
                    pass
                del temp_file_paths[filename]
            return {"status": "success", "message": f"Removed {filename}"}
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/api/upload-directory", tags=["files"], summary="Upload a directory of DICOM slices (multipart, up to 10k files)")
async def upload_directory(request: Request):
    """Upload a directory of medical image files. Supports up to 10k files."""
    from starlette.formparsers import MultiPartParser
    parser = MultiPartParser(request.headers, request.stream(), max_files=10000, max_fields=10000)
    multipart = await parser.parse()
    files = multipart.multi_items()
    # Filter to just UploadFile objects
    files = [v for k, v in files if hasattr(v, 'read')]
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
async def get_available_tools():
    return agent_decision.available_tools

@app.get("/api/enabled-tools", tags=["agent"], summary="List tools currently enabled for the agent")
async def get_enabled_tools():
    return list(agent_decision.agent_tools)

@app.post("/api/enable-tool", tags=["agent"], summary="Enable a specific MCP tool for the agent")
async def enable_tool(data: dict = Body(...)):
    tool_name = data.get("tool_name")
    if not tool_name:
        return {"error": "tool_name required"}
    agent_decision.enable_tool(tool_name)
    if data.get("notify", True):
        _push_notification("tool_enabled", f"Tool enabled: {tool_name}")
    return {"status": "enabled", "tool": tool_name}

@app.post("/api/disable-tool", tags=["agent"], summary="Disable a specific MCP tool from the agent")
async def disable_tool(data: dict = Body(...)):
    tool_name = data.get("tool_name")
    if not tool_name:
        return {"error": "tool_name required"}
    agent_decision.disable_tool(tool_name)
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
async def refresh_config():
    await agent_decision.refresh_available_tools()
    return {"status": "refreshed", "available_tools": list(agent_decision.available_tools.keys())}


@app.get("/api/notifications", tags=["agent"], summary="Get MCP event notifications")
async def get_notifications():
    return {"notifications": list(_mcp_notifications)}


@app.post("/api/refresh-server-tools", tags=["agent"], summary="Re-query tools from an already-connected MCP server")
async def refresh_server_tools(data: dict = Body(...)):
    name = data.get("name")
    if not name:
        return {"error": "name is required"}
    try:
        new_tools = await agent_decision.refresh_server_tools(name)
        return {"status": "refreshed", "server": name, "tools": list(new_tools.keys())}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/add-mcp-server", tags=["agent"], summary="Connect a new MCP server live without restarting")
async def add_mcp_server(data: dict = Body(...)):
    name = data.get("name")
    cfg = data.get("config")
    if not name or not cfg:
        return {"error": "name and config are required"}
    try:
        new_tools = await agent_decision.add_mcp_server(name, cfg)
        _push_notification("server_added", f"MCP server connected: {name} ({len(new_tools)} tools)")
        for tool in new_tools:
            _push_notification("tool_added", f"New tool available: {tool}")
        return {"status": "connected", "server": name, "tools": list(new_tools.keys())}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/remove-mcp-server", tags=["agent"], summary="Disconnect and remove an MCP server")
async def remove_mcp_server(data: dict = Body(...)):
    name = data.get("name")
    if not name:
        return {"error": "name is required"}
    try:
        removed_tools = [k for k in agent_decision.available_tools if k.startswith(f"{name}.")]
        await agent_decision.remove_mcp_server(name)
        _push_notification("server_removed", f"MCP server removed: {name}")
        for tool in removed_tools:
            _push_notification("tool_removed", f"Tool removed: {tool}")
        return {"status": "removed", "server": name}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/start-healthcare-conversation", tags=["agent"], summary="Set patient context for the AI agent")
async def start_healthcare_conversation(request: Request):
    """Start a healthcare conversation focused on a specific patient"""
    try:
        data = await request.json()
        patient_id = data.get("patient_id")
        patient_name = data.get("patient_name")
        
        if not patient_id or not patient_name:
            return {"error": "patient_id and patient_name are required"}
        
        # Set the agent to focus on this patient
        agent_decision.set_patient_focus(patient_id, patient_name)
        
        return {
            "status": "success",
            "message": f"Healthcare conversation started for patient {patient_name}",
            "patient_id": patient_id,
            "patient_name": patient_name
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/pending-tool", tags=["agent"], summary="Get the tool call awaiting user confirmation (debug mode)")
async def get_pending_tool():
    """Get the current pending tool call awaiting confirmation"""
    pending = agent_decision.get_pending_tool()
    if pending:
        return {
            "pending": True,
            "tool_name": pending["tool_name"],
            "arguments": pending["arguments"]
        }
    return {"pending": False}


@app.post("/api/confirm-tool", tags=["agent"], summary="Confirm and execute the pending tool call")
async def confirm_tool():
    """Confirm and execute the pending tool"""
    try:
        result = await agent_decision.confirm_tool_execution(session_id=current_session_id)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Tool execution failed: {e}")


@app.post("/api/deny-tool", tags=["agent"], summary="Cancel the pending tool call")
async def deny_tool():
    """Deny/cancel the pending tool execution"""
    result = agent_decision.deny_tool_execution()
    return {"result": result}



@app.post("/api/clear-files", tags=["files"], summary="Clear the in-memory uploaded file buffer")
async def clear_files():
    """Clear in-memory file buffer"""
    global uploaded_files, temp_file_paths
    temp_file_paths.clear()
    uploaded_files.clear()
    uploaded_dirs.clear()
    return {"status": "cleared"}


@app.post("/api/reset-session", tags=["sessions"], summary="Start a fresh session — clears context, LLM history, and uploaded files")
async def reset_session():
    """Start a fresh session - clears context and LLM history, creates new session"""
    global current_session_id, uploaded_files, temp_file_paths
    temp_file_paths.clear()
    uploaded_files.clear()
    uploaded_dirs.clear()
    agent_decision.reset_session_context()
    if agent_decision.llm_client:
        agent_decision.llm_client.start_chat()
    # Create a new session
    current_session_id = db.create_session()
    return {"status": "session_reset", "session_id": current_session_id}


# --- Session Management ---

@app.post("/api/save-session", tags=["sessions"], summary="Persist the current session with a display name")
async def save_session(data: dict = Body(...)):
    """Save/persist the current session with a name"""
    name = data.get("name")
    if not name:
        return {"error": "name is required"}
    db.update_session(current_session_id, name=name, persisted=True)
    # Save current in-memory context to DB
    agent_decision.save_context_to_db(current_session_id)
    return {"status": "saved", "session_id": current_session_id, "name": name}


@app.get("/api/sessions", tags=["sessions"], summary="List all sessions (optionally filter to persisted only)")
async def list_sessions(persisted_only: bool = False):
    """List all sessions"""
    sessions = db.list_sessions(persisted_only=persisted_only)
    for s in sessions:
        files = db.get_session_files(s["id"])
        s["file_count"] = len(files)
        s["total_size"] = db.get_session_total_size(s["id"])
    return {"sessions": sessions, "current_session_id": current_session_id}


@app.delete("/api/delete-session", tags=["sessions"], summary="Delete a saved session and its associated files")
async def delete_session(data: dict = Body(...)):
    """Delete a session and all its files"""
    global current_session_id
    session_id = data.get("session_id")
    if not session_id:
        return {"error": "session_id is required"}
    if session_id == current_session_id:
        return {"error": "Cannot delete the active session. Switch to another session first."}
    session = db.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    db.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.delete("/api/delete-all-sessions", tags=["sessions"], summary="Delete all sessions except the currently active one")
async def delete_all_sessions():
    """Delete all saved sessions except the currently active one."""
    sessions = db.list_sessions()
    deleted = []
    for s in sessions:
        if s["id"] != current_session_id:
            db.delete_session(s["id"])
            deleted.append(s["id"])
    return {"status": "deleted", "count": len(deleted)}


@app.post("/api/load-session", tags=["sessions"], summary="Load a saved session — restores context and file references")
async def load_session(data: dict = Body(...)):
    """Load a saved session - restores context and file references"""
    global current_session_id, uploaded_files, temp_file_paths
    session_id = data.get("session_id")
    if not session_id:
        return {"error": "session_id is required"}

    session = db.get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    # Switch to this session
    current_session_id = session_id
    uploaded_files.clear()
    temp_file_paths.clear()

    # Restore uploaded directories from DB
    session_files_all = db.get_session_files(session_id)
    uploaded_dirs.clear()
    for f in session_files_all:
        if f.get("file_type") == "dicom_dir" and os.path.isdir(f["stored_path"]):
            uploaded_dirs.append(f["stored_path"])

    # Restore context into the agent
    agent_decision.load_context_from_db(session_id)

    # Restore conversation messages and rebuild LLM chat history
    saved_messages = db.get_messages(session_id)
    if agent_decision.llm_client and saved_messages:
        from google.genai import types as genai_types
        history = []
        for msg in saved_messages:
            role = "user" if msg["role"] == "user" else "model"
            history.append(genai_types.Content(role=role, parts=[genai_types.Part(text=msg["content"])]))
        agent_decision.llm_client.start_chat(history=history)
    elif agent_decision.llm_client:
        agent_decision.llm_client.start_chat()

    # Restore patient focus if session had one
    if session.get("patient_id") and session.get("patient_name"):
        agent_decision.set_patient_focus(session["patient_id"], session["patient_name"])

    return {
        "status": "loaded",
        "session_id": session_id,
        "name": session["name"],
        "files": db.get_session_files(session_id),
        "messages": saved_messages
    }


@app.get("/api/session-files", tags=["sessions"], summary="Get uploaded files for a session (defaults to current session)")
async def get_session_files(session_id: Optional[str] = None):
    """Get files for a session (defaults to current)"""
    sid = session_id or current_session_id
    files = db.get_session_files(sid)
    return {"session_id": sid, "files": files}


@app.get("/api/messages", tags=["sessions"], summary="Get conversation messages for a session")
async def get_messages(session_id: Optional[str] = None):
    """Get saved conversation messages for a session (defaults to current)"""
    sid = session_id or current_session_id
    messages = db.get_messages(sid)
    return {"session_id": sid, "messages": messages}



# --- Test Endpoints: Direct MONAI Tool Calls ---
# These bypass the LLM agent entirely and call MCP tools directly via tool_registry.
# Used by the frontend "Test" tab for manually stepping through the inference pipeline
# (select file -> analyze -> pick model -> download -> run inference).

@app.get("/api/monai/sample-data", tags=["monai"], summary="List available sample/test medical image files and DICOM series directories")
async def list_sample_data():
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
async def validate_series(data: dict = Body(...)):
    """Validate a DICOM series directory using utils.parse_dicom_directory"""
    dir_path = data.get("path")
    if not dir_path or not os.path.isdir(dir_path):
        raise HTTPException(status_code=400, detail="Valid directory path is required")

    # Check if this is an image directory (JPEG/PNG) - not a DICOM series
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
        result = await agent_decision.tool_registry.execute_tool(
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
async def monai_analyze(data: dict = Body(...)):
    """Analyze a medical image - direct MONAI tool call"""
    path = data.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    result = await agent_decision.tool_registry.execute_tool(
        "monai.analyze_image", {"path": path}, logs=True
    )
    return result


@app.post("/api/monai/list-models", tags=["monai"], summary="List available MONAI model bundles (filterable by category, modality, body part)")
async def monai_list_models(data: dict = Body(...)):
    """List available MONAI models"""
    args = {}
    if data.get("category"):
        args["category"] = data["category"]
    if data.get("modality"):
        args["modality"] = data["modality"]
    if data.get("body_part"):
        args["body_part"] = data["body_part"]
    result = await agent_decision.tool_registry.execute_tool(
        "monai.list_models", args, logs=True
    )
    return result


@app.post("/api/monai/download-model", tags=["monai"], summary="Download a MONAI Model Zoo bundle by name")
async def monai_download_model(data: dict = Body(...)):
    """Download a model bundle from MONAI Model Zoo"""
    model_name = data.get("model_name")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")
    result = await agent_decision.tool_registry.execute_tool(
        "monai.download_model", {"model_name": model_name}, logs=True
    )
    return result


@app.post("/api/monai/run-inference", tags=["monai"], summary="Run MONAI inference on a medical image with a specified model")
async def monai_run_inference(data: dict = Body(...)):
    """Run inference on a medical image"""
    image_path = data.get("image_path")
    model_name = data.get("model_name")
    if not image_path or not model_name:
        raise HTTPException(status_code=400, detail="image_path and model_name required")
    result = await agent_decision.tool_registry.execute_tool(
        "monai.run_inference",
        {"image_path": image_path, "model_name": model_name},
        logs=True
    )
    return result


@app.get("/api/patients", tags=["system"], summary="Get patient list from FHIR server (falls back to mock data if unavailable)")
async def get_patients():
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
async def sse_events(request: Request):
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

            # Pre-populate so we don't fire stale notifications on reconnect.
            notified: set = set()   # tasks already sent done/failed event
            started: set = set()    # tasks already sent running event
            seen_ids: set = set()   # all task IDs ever seen (to detect brand-new tasks)
            try:
                for t in db.list_tasks():
                    seen_ids.add(t["id"])
                    if t["status"] in ("done", "failed"):
                        notified.add(t["id"])
                    if t["status"] in ("running", "done", "failed"):
                        started.add(t["id"])
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
                    tasks = db.list_tasks()
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

                    if tid in notified or status not in ("done", "failed"):
                        continue

                    event_type = "task_done" if status == "done" else "task_failed"
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
                if keepalive_ticks >= 25:
                    yield ": keepalive\n\n"
                    keepalive_ticks = 0

        except BaseException:
            return  # Swallow any thrown exception so the generator closes cleanly

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/tasks", tags=["events"], summary="List background inference/report tasks, optionally filtered by session")
async def list_tasks(session_id: Optional[str] = None):
    """Return all background tasks, optionally filtered by session_id."""
    tasks = db.list_tasks(session_id=session_id)
    return {"tasks": tasks}


@app.post("/api/generate-report", tags=["events"], summary="Queue a radiology report generation task from selected inference results")
async def generate_report(data: dict = Body(...)):
    """
    Queue a report-generation background task from selected inference results.
    Body: {task_ids: [...], patient_context: {...}}
    """
    task_ids = data.get("task_ids", [])
    if not task_ids:
        raise HTTPException(status_code=400, detail="task_ids is required")

    patient_context = data.get("patient_context", {})
    description = f"Report from {len(task_ids)} inference result(s)"

    task_id = task_runner.submit_task(
        session_id=current_session_id,
        task_type="report",
        description=description,
        input_data={"task_ids": task_ids, "patient_context": patient_context},
    )

    return {"status": "queued", "task_id": task_id, "description": description}


@app.get("/api/health", tags=["system"], summary="Health check")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:5001")
    uvicorn.run(app, host="0.0.0.0", port=5001, timeout_graceful_shutdown=3)

