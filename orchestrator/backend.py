#!/usr/bin/env python3
from email.mime import image
import json
import os
import tempfile
import python_multipart
from typing import AsyncGenerator, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
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





@app.get("/api/process-query")
async def process_query(query: str):
    print(f"Processing query: {query}")

    print("Uploaded files list:", uploaded_files)
    result = agent_decision.execute_task(query, imageList=uploaded_files)
    return {"result": result}



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
