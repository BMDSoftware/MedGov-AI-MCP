#!/usr/bin/env python3
import asyncio
from email.mime import image
import json
import os
import tempfile
import python_multipart
from typing import AsyncGenerator, Optional
from dotenv import load_dotenv

# Load env BEFORE importing agenticAgent so LLM_BACKEND is set
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from agenticAgent import agent_decision

workflow_queue = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    await agent_decision._initialize_components()
    yield
    # Shutdown code - clean up files and close MCP sessions
    uploaded_files.clear()
    for temp_path in temp_file_paths.values():
        try:
            os.unlink(temp_path)
        except:
            pass
    temp_file_paths.clear()

    # Close MCP sessions properly
    try:
        await agent_decision.close()
    except Exception as e:
        print(f"Error closing agent: {e}")

app = FastAPI(title="Agentic Health Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploaded_files = []  # Store uploaded files in memory
temp_file_paths = {}  # Store temporary file paths for processing


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

@app.post("/api/process-workflow")
async def process_workflow(data: dict = Body(default=None)):
    global uploaded_files, image_metadata

    # Check for action type
    action = data.get("action") if data else None

    # Handle report generation separately
    if action == "generate_report":
        analysis = data.get("analysis", {})
        return await generate_report(analysis)

    # Get modality from request body if provided
    modality = None
    body_part = None
    if data:
        modality = data.get("modality") or image_metadata.get("modality")
        body_part = data.get("bodyPart") or image_metadata.get("bodyPart")

    # Build query with modality context if available
    if modality and body_part:
        query = f"This is a {modality} scan of the {body_part}. Follow all steps: analyze the image, list models, download the best model, and run inference. Return the segmentation/detection results."
    else:
        query = "Analyze this medical image, download an appropriate model, run inference, and return the AI analysis results. Follow all workflow steps."

    print(f"Starting predefined workflow: {query}")
    print("Uploaded files list:", uploaded_files)

    if not uploaded_files:
        return {"result": {"error": "No files uploaded. Please upload an image first."}}
    
    # Create temporary files and prepare tuples with (temp_filepath, content)
    image_data = []
    try:
        for filename, contents in uploaded_files:
            # Create temporary file with original extension
            # Handle double extensions like .nii.gz
            if filename.endswith('.nii.gz'):
                file_extension = '.nii.gz'
            else:
                file_extension = os.path.splitext(filename)[1] or '.tmp'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
            temp_file.write(contents)
            temp_file.close()
            temp_file_paths[filename] = temp_file.name
            
            # Add tuple of (temp_filepath, content) to the list
            image_data.append((temp_file.name, contents))
            print(f"Saved {filename} to {temp_file.name}")
        
        # Pass metadata for model filtering (lowercase body_part to match registry)
        metadata = {
            "modality": modality,
            "body_part": body_part.lower() if body_part else None
        }
        result = await agent_decision.execute_task(query, imageList=image_data, metadata=metadata)

        # Keep files in memory for subsequent workflows (e.g., report generation)
        # Files will be cleared on backend shutdown or manual clear

        return {"result": result}
        
    except Exception as e:
        print(f"Error processing workflow: {e}")
        # Clean up temporary files on error
        for temp_path in temp_file_paths.values():
            try:
                os.unlink(temp_path)
            except:
                pass
        temp_file_paths.clear()
        return {"result": {"error": str(e)}}
    

    
@app.post("/api/process-query")
async def process_query(query: str = Body(..., media_type="text/plain")):
    print(f"Processing ad-hoc query: {query}")
    try:
        if not uploaded_files:
            result = await agent_decision.execute_task(query, )
        else:
            # Use existing uploaded files
            image_data = []
            try:
                for filename, contents in uploaded_files:
                    # Create temporary file with original extension
                    # Handle double extensions like .nii.gz
                    if filename.endswith('.nii.gz'):
                        file_extension = '.nii.gz'
                    else:
                        file_extension = os.path.splitext(filename)[1] or '.tmp'
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
                    temp_file.write(contents)
                    temp_file.close()
                    temp_file_paths[filename] = temp_file.name
                    
                    # Add tuple of (temp_filepath, content) to the list
                    image_data.append((temp_file.name, contents))
                    print(f"Saved {filename} to {temp_file.name}")
                
                
                result = await agent_decision.execute_task(query, imageList=image_data)
            except Exception as e:
                print(f"Error preparing files for query: {e}")
                return {"result": {"error": str(e)}}
        return {"result": result}
    except Exception as e:
        print(f"Error processing query: {e}")
        return {"result": {"error": str(e)}}



@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    global uploaded_files, temp_file_paths
    print(f"Received file: {file.filename}")
    try:
        # Clear previous files when uploading a new one
        for temp_path in temp_file_paths.values():
            try:
                os.unlink(temp_path)
            except:
                pass
        temp_file_paths.clear()
        uploaded_files.clear()

        contents = await file.read()
        uploaded_files.append((file.filename, contents))
        print(f"Uploaded files list now has {len(uploaded_files)} file(s)")
        return {"status": "success", "filename": file.filename, "size": len(contents)}
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
    result = await agent_decision.confirm_tool_execution()
    return {"result": result}


@app.post("/api/deny-tool")
async def deny_tool():
    """Deny/cancel the pending tool execution"""
    result = agent_decision.deny_tool_execution()
    return {"result": result}


async def generate_report(analysis: dict):
    """Generate a clinical report from inference results using RadLex tools directly"""
    print(f"Generating report from analysis: {analysis}")

    # Extract inference results
    inference_result = analysis.get("inference_result", {})
    results = inference_result.get("results", {})
    detected_structures = results.get("detected_structures", [])
    model_used = inference_result.get("model_used", "unknown")
    model_type = inference_result.get("model_type", "segmentation")
    labels = inference_result.get("labels", {})

    try:
        # Step 1: List templates to find the right one
        templates_result = await agent_decision.tool_registry.execute_tool(
            "radlex.list_templates",
            {"modality": "CT", "body_part": "abdomen"}
        )
        print(f"Templates found: {templates_result}")

        # Pick the first matching template or default to ct_abdomen_general
        template_id = "ct_abdomen_general"
        if templates_result and templates_result.get("templates"):
            template_id = templates_result["templates"][0]["id"]

        # Step 2: Build findings from AI analysis
        # Mark all organs as not analyzed by default
        findings = {
            "liver_findings": "Not analyzed.",
            "gallbladder_findings": "Not analyzed.",
            "spleen_findings": "Not analyzed.",
            "pancreas_findings": "Not analyzed.",
            "adrenal_findings": "Not analyzed.",
            "kidney_findings": "Not analyzed.",
            "bladder_findings": "Not analyzed.",
            "bowel_findings": "Not analyzed.",
            "lymph_node_findings": "Not analyzed.",
            "vascular_findings": "Not analyzed.",
            "bone_findings": "Not analyzed.",
            "other_findings": "None.",
        }

        # Fill in actual AI findings
        analyzed_structures = []
        for struct in detected_structures:
            name = struct.get("name", "").lower()
            voxels = struct.get("voxel_count", 0)
            vol_pct = struct.get("volume_percentage", 0)
            analyzed_structures.append(struct.get("name", "unknown"))

            if "spleen" in name:
                findings["spleen_findings"] = f"Segmented. Volume: {voxels:,} voxels ({vol_pct}% of image)."
            elif "liver" in name:
                findings["liver_findings"] = f"Segmented. Volume: {voxels:,} voxels ({vol_pct}% of image)."
            elif "kidney" in name:
                findings["kidney_findings"] = f"Segmented. Volume: {voxels:,} voxels ({vol_pct}% of image)."
            elif "pancreas" in name:
                findings["pancreas_findings"] = f"Segmented. Volume: {voxels:,} voxels ({vol_pct}% of image)."
            elif "tumor" in name:
                findings["other_findings"] = f"TUMOR DETECTED. Volume: {voxels:,} voxels ({vol_pct}% of image). Urgent review required."
            elif "nodule" in name:
                findings["other_findings"] = f"NODULE DETECTED. Volume: {voxels:,} voxels. Further evaluation recommended."

        # Add technique info
        findings["clinical_history"] = "AI-assisted image analysis"
        findings["comparison"] = "None"
        findings["contrast"] = "as provided in source image"

        # Build impression
        if detected_structures:
            findings["impression"] = f"""1. AI segmentation complete using {model_used}.
2. Analyzed: {', '.join(analyzed_structures)}.
3. Other structures not evaluated.
4. Radiologist review required."""
        else:
            findings["impression"] = """1. No structures detected by AI.
2. Radiologist review required."""

        # Step 3: Generate the report
        report_result = await agent_decision.tool_registry.execute_tool(
            "radlex.generate_report",
            {
                "template_id": template_id,
                "findings": findings,
                "patient_info": {"name": "Anonymous", "mrn": "N/A"}
            }
        )
        print(f"Report generated: {report_result}")

        if report_result and report_result.get("report_text"):
            return {
                "result": {
                    "answer": report_result["report_text"],
                    "report": report_result["report_text"],
                    "template_used": template_id,
                    "success": True
                }
            }
        else:
            raise Exception("Report generation returned no text")

    except Exception as e:
        print(f"Report generation error: {e}")
        # Fallback: generate a simple report
        findings_text = "\n".join([
            f"- {s.get('name', 'unknown')}: {s.get('voxel_count', 0)} voxels ({s.get('volume_percentage', 0)}%)"
            for s in detected_structures
        ]) or "No structures detected"

        report = f"""
============================================================
RADIOLOGY REPORT - CT ABDOMEN (AI-GENERATED)
============================================================
Exam Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}
------------------------------------------------------------

CLINICAL HISTORY:
AI-assisted medical image analysis

TECHNIQUE:
{model_type.upper()} analysis using {model_used} model.
Processing performed on CUDA GPU.

FINDINGS:
{findings_text}

IMPRESSION:
1. Automated {model_type} analysis completed.
2. Results should be reviewed and validated by a qualified radiologist.
3. This AI-generated report is for research/demonstration purposes only.

------------------------------------------------------------
Report generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
AI Assistant: HealthMCP
============================================================
"""
        return {"result": {"answer": report, "report": report, "fallback": True}}



@app.post("/api/clear-files")
async def clear_files():
    """Manually clear uploaded files"""
    global uploaded_files, temp_file_paths
    for temp_path in temp_file_paths.values():
        try:
            os.unlink(temp_path)
        except:
            pass
    temp_file_paths.clear()
    uploaded_files.clear()
    return {"status": "cleared"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}



if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:5001")
    uvicorn.run(app, host="0.0.0.0", port=5001)

