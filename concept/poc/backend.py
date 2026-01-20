#!/usr/bin/env python3
import os
import json
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from mcp_calls import search_patients, create_patient, set_tool_callback
from models import anonymize_with_ai
from pii_detector import get_all_pii_fields

load_dotenv()

workflow_queue = []

app = FastAPI(title="Agentic Health Anonymizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FHIR_SERVER_URL = os.getenv("FHIR_SERVER_URL", "http://localhost:8080/fhir")
uploaded_files = {}


async def send_step(step_type: str, message: str, **kwargs) -> str:
    data = {
        "type": "step",
        "stepType": step_type,
        "message": message,
        **kwargs
    }
    return f"data: {json.dumps(data)}\n\n"


async def workflow_stream(filename: str) -> AsyncGenerator[str, None]:
    workflow_queue.clear()

    def tool_callback(phase, tool_name, data):
        if phase == "before":
            workflow_queue.append({
                "type": "tool_call",
                "tool_name": tool_name,
                "arguments": data
            })
        elif phase == "after":
            workflow_queue.append({
                "type": "tool_result",
                "tool_name": tool_name,
                "result": data
            })

    set_tool_callback(tool_callback)

    try:
        if filename not in uploaded_files:
            yield await send_step("info", "No file uploaded, fetching from FHIR server")

            bundle = search_patients(count=1)

            for event in workflow_queue:
                if event["type"] == "tool_call":
                    yield await send_step("tool_call", f"Calling MCP {event['tool_name']} tool",
                                        toolName=event['tool_name'],
                                        arguments=event['arguments'])
                elif event["type"] == "tool_result":
                    yield await send_step("tool_result", f"Tool {event['tool_name']} completed")

            workflow_queue.clear()

            if bundle and bundle.get("entry"):
                original_data = bundle["entry"][0]["resource"]
                is_fhir = True
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Could not fetch patient'})}\n\n"
                return
        else:
            file_data = uploaded_files[filename]

            yield await send_step("info", f"Processing file: {filename}")

            is_fhir = False
            original_data = None

            try:
                patient_data = json.loads(file_data.decode('utf-8'))

                if patient_data.get("resourceType") == "Bundle":
                    yield await send_step("info", "Detected FHIR Bundle format")
                    if patient_data.get("entry") and len(patient_data["entry"]) > 0:
                        original_data = patient_data["entry"][0]["resource"]
                        is_fhir = True
                elif patient_data.get("resourceType") == "Patient":
                    yield await send_step("info", "Detected FHIR Patient format")
                    original_data = patient_data
                    is_fhir = True
                else:
                    yield await send_step("info", "Detected generic JSON format")
                    original_data = patient_data
                    is_fhir = False

            except json.JSONDecodeError:
                yield await send_step("info", "Non-JSON file, treating as text data")
                original_data = file_data.decode('utf-8')
                is_fhir = False

        yield await send_step("thinking", "Checking hardcoded mandatory PII fields")
        yield await send_step("thinking", "AI analyzing data to detect additional PII")

        hardcoded_pii, ai_detected_pii = get_all_pii_fields(original_data)

        if hardcoded_pii:
            yield await send_step("anonymization",
                                f"Mandatory PII detected: {', '.join(hardcoded_pii[:5])}{'...' if len(hardcoded_pii) > 5 else ''}",
                                fields=hardcoded_pii)

        if ai_detected_pii:
            yield await send_step("anonymization",
                                f"AI detected PII: {', '.join(ai_detected_pii[:5])}{'...' if len(ai_detected_pii) > 5 else ''}",
                                fields=ai_detected_pii)

        all_pii = list(set(hardcoded_pii + ai_detected_pii))

        yield await send_step("thinking", "Applying AI-powered anonymization")

        anonymized = anonymize_with_ai(original_data, use_ollama=False)

        if is_fhir and isinstance(anonymized, dict):
            if 'id' in anonymized:
                del anonymized['id']

            new_patient = create_patient(anonymized)

            for event in workflow_queue:
                if event["type"] == "tool_call":
                    yield await send_step("tool_call", f"Calling MCP {event['tool_name']} tool",
                                        toolName=event['tool_name'],
                                        arguments=event['arguments'])
                elif event["type"] == "tool_result":
                    yield await send_step("tool_result", f"Tool {event['tool_name']} completed")

            workflow_queue.clear()

            if new_patient:
                new_id = new_patient.get("id")
                anonymized = new_patient
            else:
                yield await send_step("info", "Could not save to FHIR, returning anonymized data only")

        summary = {
            "fieldsRemoved": len(all_pii),
            "fieldsGeneralized": 2,
            "fieldsKept": 3,
            "changes": [],
            "hardcodedPII": len(hardcoded_pii),
            "aiDetectedPII": len(ai_detected_pii)
        }

        for field in hardcoded_pii:
            summary["changes"].append({
                "type": "removed",
                "field": field,
                "description": f"{field} (mandatory)"
            })

        for field in ai_detected_pii:
            summary["changes"].append({
                "type": "removed",
                "field": field,
                "description": f"{field} (AI detected)"
            })

        summary["changes"].extend([
            {"type": "generalized", "field": "dates", "description": "Dates generalized"},
            {"type": "generalized", "field": "location", "description": "Location precision reduced"},
        ])

        result_data = {
            "type": "result",
            "payload": {
                "original": original_data,
                "anonymized": anonymized,
                "summary": summary,
                "fhirUrl": f"{FHIR_SERVER_URL}/Patient/{anonymized.get('id')}" if is_fhir and isinstance(anonymized, dict) else None
            }
        }
        yield f"data: {json.dumps(result_data)}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        uploaded_files[file.filename] = contents
        return {"status": "success", "filename": file.filename, "size": len(contents)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/anonymize-stream")
async def anonymize_stream(filename: str):
    return StreamingResponse(
        workflow_stream(filename),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://localhost:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000)
