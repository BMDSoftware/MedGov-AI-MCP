#!/usr/bin/env python3
import asyncio
import json
import os
import shutil
import uuid
import python_multipart
from typing import Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Load env BEFORE importing agenticAgent so LLM_BACKEND is set
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from agenticAgent import agent_decision
import database as db

current_session_id: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global current_session_id
    # Startup
    db.init_db()
    current_session_id = db.create_session()
    await agent_decision._initialize_components()
    yield
    # Shutdown - close MCP sessions
    agent_decision.reset_session_context()
    try:
        await agent_decision.close()
    except BaseException:
        pass

app = FastAPI(title="Agentic Health Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploaded_files = []  # In-memory buffer for current upload (before query)
temp_file_paths = {}  # Temp file paths mapped by filename


async def send_step(step_type: str, message: str, **kwargs) -> str:
    data = {
        "type": "step",
        "stepType": step_type,
        "message": message,
        **kwargs
    }
    return f"data: {json.dumps(data)}\n\n"





# Store metadata from frontend
image_metadata = {"modality": None, "bodyPart": None}

@app.post("/api/set-metadata")
async def set_metadata(data: dict = Body(...)):
    global image_metadata
    image_metadata["modality"] = data.get("modality")
    image_metadata["bodyPart"] = data.get("bodyPart")
    return {"status": "ok"}


    
@app.post("/api/process-query")
async def process_query(query: str = Body(..., media_type="text/plain")):
    print(f"Processing ad-hoc query: {query}")
    try:
        # Get files for current session from DB (persistent paths)
        session_files = db.get_session_files(current_session_id)

        if not uploaded_files and not session_files:
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
                # Load from persistent storage
                for f in session_files:
                    path = f["stored_path"]
                    if os.path.exists(path):
                        with open(path, "rb") as fh:
                            contents = fh.read()
                        image_data.append((path, contents))
                        print(f"Using DB file: {path}")

            if image_data:
                result = await agent_decision.execute_task(query, imageList=image_data, session_id=current_session_id)
            else:
                result = await agent_decision.execute_task(query, session_id=current_session_id)

        return {"result": result}
    except Exception as e:
        print(f"Error processing query: {e}")
        return {"result": {"error": str(e)}}



@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    global uploaded_files, temp_file_paths
    print(f"Received file: {file.filename}")
    try:
        # Clear previous in-memory buffer
        uploaded_files.clear()
        temp_file_paths.clear()

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
    

@app.delete("/api/upload")
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
                except:
                    pass
                del temp_file_paths[filename]
            return {"status": "success", "message": f"Removed {filename}"}
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/api/upload-directory")
async def upload_directory(files: List[UploadFile] = File(...)):
    """Upload a directory of DICOM slices. Stores all files in a subdirectory under uploads."""
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
            # Skip non-DICOM junk files
            if fname.startswith('.') or fname.endswith(('.png', '.sql', '.txt', '.zip')):
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


@app.get("/api/available-tools")
async def get_available_tools():
    # Returns all available tools, grouped by tool name
    return agent_decision.available_tools

@app.get("/api/enabled-tools")
async def get_enabled_tools():
    # Returns a list of enabled tool names
    return list(agent_decision.agent_tools)

@app.post("/api/enable-tool")
async def enable_tool(data: dict = Body(...)):
    tool_name = data.get("tool_name")
    if not tool_name:
        return {"error": "tool_name required"}
    agent_decision.enable_tool(tool_name)
    return {"status": "enabled", "tool": tool_name}

@app.post("/api/disable-tool")
async def disable_tool(data: dict = Body(...)):
    tool_name = data.get("tool_name")
    if not tool_name:
        return {"error": "tool_name required"}
    agent_decision.disable_tool(tool_name)
    return {"status": "disabled", "tool": tool_name}


@app.post("/api/refresh-config")
async def refresh_config():
    await agent_decision.refresh_available_tools()
    return {"status": "refreshed", "available_tools": list(agent_decision.available_tools.keys())}


@app.post("/api/start-healthcare-conversation")
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


@app.get("/api/pending-tool")
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


@app.post("/api/confirm-tool")
async def confirm_tool():
    """Confirm and execute the pending tool"""
    result = await agent_decision.confirm_tool_execution(session_id=current_session_id)
    return {"result": result}


@app.post("/api/deny-tool")
async def deny_tool():
    """Deny/cancel the pending tool execution"""
    result = agent_decision.deny_tool_execution()
    return {"result": result}



@app.post("/api/clear-files")
async def clear_files():
    """Clear in-memory file buffer"""
    global uploaded_files, temp_file_paths
    temp_file_paths.clear()
    uploaded_files.clear()
    return {"status": "cleared"}


@app.post("/api/reset-session")
async def reset_session():
    """Start a fresh session - clears context and LLM history, creates new session"""
    global current_session_id, uploaded_files, temp_file_paths
    temp_file_paths.clear()
    uploaded_files.clear()
    agent_decision.reset_session_context()
    if agent_decision.llm_client:
        agent_decision.llm_client.start_chat()
    # Create a new session
    current_session_id = db.create_session()
    return {"status": "session_reset", "session_id": current_session_id}


# --- Session Management ---

@app.post("/api/save-session")
async def save_session(data: dict = Body(...)):
    """Save/persist the current session with a name"""
    name = data.get("name")
    if not name:
        return {"error": "name is required"}
    db.update_session(current_session_id, name=name, persisted=True)
    # Save current in-memory context to DB
    agent_decision.save_context_to_db(current_session_id)
    return {"status": "saved", "session_id": current_session_id, "name": name}


@app.get("/api/sessions")
async def list_sessions(persisted_only: bool = False):
    """List all sessions"""
    sessions = db.list_sessions(persisted_only=persisted_only)
    for s in sessions:
        files = db.get_session_files(s["id"])
        s["file_count"] = len(files)
        s["total_size"] = db.get_session_total_size(s["id"])
    return {"sessions": sessions, "current_session_id": current_session_id}


@app.delete("/api/delete-session")
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


@app.post("/api/load-session")
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

    # Restore context into the agent
    agent_decision.load_context_from_db(session_id)

    # Reset LLM chat (context comes from SessionContext injection, not chat history)
    if agent_decision.llm_client:
        agent_decision.llm_client.start_chat()

    # Restore patient focus if session had one
    if session.get("patient_id") and session.get("patient_name"):
        agent_decision.set_patient_focus(session["patient_id"], session["patient_name"])

    return {
        "status": "loaded",
        "session_id": session_id,
        "name": session["name"],
        "files": db.get_session_files(session_id)
    }


@app.get("/api/session-files")
async def get_session_files(session_id: Optional[str] = None):
    """Get files for a session (defaults to current)"""
    sid = session_id or current_session_id
    files = db.get_session_files(sid)
    return {"session_id": sid, "files": files}





# --- Test Endpoints: Direct MONAI Tool Calls ---
# These bypass the LLM agent entirely and call MCP tools directly via tool_registry.
# Used by the frontend "Test" tab for manually stepping through the inference pipeline
# (select file -> analyze -> pick model -> download -> run inference).

@app.get("/api/monai/sample-data")
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
                slice_count = sum(1 for f in d.iterdir() if f.is_file() and not f.name.startswith('.'))
                if slice_count > 0:
                    total_size = sum(f.stat().st_size for f in d.iterdir() if f.is_file())
                    files.append({
                        "name": f"{d.name} ({slice_count} slices)",
                        "path": str(d.resolve()),
                        "size": total_size,
                        "type": "dicom_series",
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


@app.post("/api/monai/validate-series")
async def validate_series(data: dict = Body(...)):
    """Validate a DICOM series directory using utils.parse_dicom_directory"""
    dir_path = data.get("path")
    if not dir_path or not os.path.isdir(dir_path):
        raise HTTPException(status_code=400, detail="Valid directory path is required")

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


@app.post("/api/monai/analyze")
async def monai_analyze(data: dict = Body(...)):
    """Analyze a medical image - direct MONAI tool call"""
    path = data.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    result = await agent_decision.tool_registry.execute_tool(
        "monai.analyze_image", {"path": path}, logs=True
    )
    return result


@app.post("/api/monai/list-models")
async def monai_list_models(data: dict = Body(...)):
    """List available MONAI models"""
    args = {}
    if data.get("category"): args["category"] = data["category"]
    if data.get("modality"): args["modality"] = data["modality"]
    if data.get("body_part"): args["body_part"] = data["body_part"]
    result = await agent_decision.tool_registry.execute_tool(
        "monai.list_models", args, logs=True
    )
    return result


@app.post("/api/monai/download-model")
async def monai_download_model(data: dict = Body(...)):
    """Download a model bundle from MONAI Model Zoo"""
    model_name = data.get("model_name")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")
    result = await agent_decision.tool_registry.execute_tool(
        "monai.download_model", {"model_name": model_name}, logs=True
    )
    return result


@app.post("/api/monai/run-inference")
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


@app.get("/api/patients")
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
                    import json
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


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}



if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:5001")
    uvicorn.run(app, host="0.0.0.0", port=5001)

