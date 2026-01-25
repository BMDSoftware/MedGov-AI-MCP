#!/usr/bin/env python3
from email.mime import image
import json
import os
import tempfile
import python_multipart
from typing import AsyncGenerator, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from agenticAgent import agent_decision

load_dotenv()

workflow_queue = []

app = FastAPI(title="Agentic Health Assistant API")

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

    # Get modality from request body if provided
    modality = None
    body_part = None
    if data:
        modality = data.get("modality") or image_metadata.get("modality")
        body_part = data.get("bodyPart") or image_metadata.get("bodyPart")

    # Build query with modality context if available
    if modality and body_part:
        query = f"This is a {modality} scan of the {body_part}. Analyse the image and return the most suitable model for analysis. If a suitable model exists, explain what it can detect. If no suitable model is found, explain and suggest the closest model available."
    else:
        query = "Analyse and return the most suitable model for the uploaded medical images and explain why. If no suitable model is found, explain and suggest the closest model available."

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
        
        result = agent_decision.execute_task(query, imageList=image_data)
        
        # Clean up temporary files after agent execution
        for temp_path in temp_file_paths.values():
            try:
                os.unlink(temp_path)
            except:
                pass
        temp_file_paths.clear()
        uploaded_files.clear()  # Clear uploaded files after processing

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
    

    



@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    print(f"Received file: {file.filename}")
    try:
        contents = await file.read()
        uploaded_files.append((file.filename, contents))
        return {"status": "success", "filename": file.filename, "size": len(contents)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:5001")
    uvicorn.run(app, host="0.0.0.0", port=5001)
