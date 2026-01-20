# Agentic Health Anonymizer - Documentation

## Overview

This system anonymizes medical patient data using AI and MCP (Model Context Protocol). It can handle any data format and intelligently detects and removes personally identifiable information while preserving medical value.

## Architecture

### Components

**Frontend (React + Vite)**
- Simple web interface on port 5173
- File upload with drag and drop
- Real-time workflow visualization showing AI thinking and tool calls
- Results display with comparison view

**Backend (FastAPI)**
- API server on port 5000
- Orchestrates the anonymization workflow
- Streams progress updates to frontend via Server-Sent Events
- Coordinates between AI model and MCP tools

**MCP Server (FHIR)**
- Runs on port 8000
- Provides tools to interact with FHIR server
- Tools: search, create, read, update, delete
- Acts as abstraction layer over FHIR API

**FHIR Server (HAPI)**
- Runs on port 8080
- Stores patient data in FHIR format
- PostgreSQL database backend
- Runs in Docker container

**Data Generator (Synthea)**
- Generates synthetic patient data
- Creates realistic FHIR bundles for testing
- Java-based tool

**AI (Gemini 2.5 Flash)**
- Performs intelligent anonymization
- Detects PII fields in any format
- Context-aware decisions on what to keep vs remove

## Code Structure

### Backend Files

**backend.py**
Main API server. Handles file uploads and orchestrates the anonymization workflow. Streams real-time updates to frontend showing each step of the process.

**models.py**
Contains AI model integration and anonymization logic. Defines mandatory PII fields and rules for anonymization. Uses Gemini API to perform intelligent anonymization.

**mcp_calls.py**
Wrapper functions for MCP tools. Provides clean interface to call FHIR operations. Includes automatic tool call tracking for workflow visualization.

**pii_detector.py**
Hybrid PII detection system. Combines hardcoded mandatory fields with AI-powered detection to find PII in any data format.

**upload_patients.py**
Utility script to upload Synthea-generated patient data to FHIR server. Extracts Patient resources from bundles.

### Frontend Files

**App.jsx**
Main application component. Manages state for workflow steps, results, and processing status. Handles SSE connection for real-time updates.

**FileUpload.jsx**
File upload component with drag and drop. Works with or without file upload. Can trigger anonymization of FHIR server data directly.

**WorkflowPanel.jsx**
Displays real-time workflow steps. Shows AI thinking, tool calls, anonymization actions. Auto-scrolls as new steps appear.

**ResultsDisplay.jsx**
Shows original vs anonymized data. Tabbed interface with comparison view, individual views, and summary. Includes download functionality.

## How It Works

### Anonymization Workflow

1. User uploads file or clicks to fetch from FHIR server
2. Backend receives request and starts workflow
3. If no file uploaded, MCP search tool fetches patient from FHIR
4. System performs hybrid PII detection:
   - Checks hardcoded mandatory PII fields
   - AI analyzes data to detect additional PII
5. AI anonymizes the data using context-aware rules
6. If FHIR format, saves anonymized patient back to FHIR via MCP create tool
7. Returns results with original, anonymized, and summary

### PII Detection (Hybrid Approach)

**Hardcoded Mandatory Fields**
Critical PII that must always be removed regardless of AI decision. Includes: name, SSN, phone, email, identifier, street address, IP address, device ID.

**AI Detection**
AI analyzes entire data structure to find PII in any field name or format. Can detect: birthDate, coordinates, mother's maiden name, any sensitive data the AI recognizes.

**Why Hybrid**
Hardcoded ensures critical PII never slips through. AI handles unknown formats and field names. Best of both worlds for reliability and flexibility.

### Anonymization Rules

**Mandatory Removal**
Full names, SSN, phone numbers, emails, patient IDs, street addresses, IP addresses, device IDs.

**Mandatory Generalization**
Birth dates reduced to year only or age ranges. Exact dates shifted or precision reduced. Postal codes masked.

**Preserved Data**
Gender, general location (city, state, country), medical conditions, diagnoses, treatments, medications, lab results, vital signs.

**Context-Aware Decisions**
For children, exact ages kept if medically critical. For adults, age ranges used. For rare conditions, additional fields generalized to prevent re-identification. Clinical notes redacted for PII but medical context kept.

## MCP Integration

### Tool Tracking

All MCP tool calls are automatically tracked and displayed in workflow. No manual coding needed when adding new tools. Callback system intercepts all tool calls and logs them.

### Available Tools

**search**
Searches FHIR server for resources. Used to fetch patients for anonymization.

**create**
Creates new resources in FHIR server. Used to save anonymized patients.

**read**
Retrieves specific resource by ID. Available for future features.

**update**
Updates existing resource. Available for future features.

**delete**
Removes resource from server. Available for future features.

### Adding New Tools

1. Add function to mcp_calls.py using _call_mcp_tool wrapper
2. Tool calls automatically appear in workflow
3. No changes needed to backend.py

## Data Flow

### File Upload Path
User uploads file -> Frontend sends to /api/upload -> Backend stores in memory -> Frontend triggers /api/anonymize-stream -> Backend processes and streams updates

### FHIR Fetch Path
User clicks button -> Frontend triggers /api/anonymize-stream with no file -> Backend calls MCP search tool -> Gets patient from FHIR -> Processes and streams updates

### Anonymization Path
Data received -> Hybrid PII detection -> AI anonymization -> MCP create (if FHIR) -> Results returned

### Streaming Updates
Backend yields step messages -> Sent as SSE events -> Frontend receives and updates UI in real-time -> User sees workflow progress live

## API Endpoints

**POST /api/upload**
Accepts file upload. Stores file in memory. Returns success status with filename and size.

**GET /api/anonymize-stream**
SSE endpoint that streams workflow updates. Takes filename parameter. Returns real-time progress events.

**GET /api/health**
Health check endpoint. Returns status healthy.

## Configuration

### Environment Variables

**GEMINI_API_KEY**
API key for Google Gemini. Required for AI anonymization.

**FHIR_SERVER_URL**
URL of FHIR server. Default is http://localhost:8080/fhir

**MCP_SERVER_URL**
URL of MCP server. Default is http://localhost:8000

### Dependencies

**Backend**
FastAPI, uvicorn, google-genai, requests, python-dotenv, python-multipart

**Frontend**
React, Vite

## Current Limitations

### Not Truly Agentic

The AI does not autonomously decide which tools to call. Backend manually orchestrates the workflow. AI only handles anonymization logic, not tool selection.

True agentic AI would give the AI direct access to MCP tools and let it decide when to call search, create, update, etc. Current implementation is scripted orchestration.

### AI Detection Performance

AI detection of PII fields adds latency. Each anonymization makes two AI calls: one to detect fields, one to anonymize. Could be optimized to single call.

### File Format Support

Currently optimized for FHIR JSON. Other formats (PDF, CSV, images) accepted but treated as text. No special parsing for non-JSON formats yet.

### Single Patient Processing

Processes one patient at a time. No batch processing support. Would need queue system for multiple patients.

## Future Improvements

### True Agentic Implementation

Use Claude API with tool use. Give Claude direct access to MCP tools. Let Claude autonomously decide workflow. Claude would chain tool calls based on task.

### Batch Processing

Add queue system for multiple files. Process patients in parallel. Progress tracking for batch operations.

### Enhanced File Support

PDF text extraction and anonymization. Image OCR and redaction. CSV parsing and column-based anonymization. HL7 message support.

### Custom MCP Tools

Add tools for file parsing. Tools for different data formats. Integration with other healthcare systems.

### Audit Trail

Log all anonymization operations. Track what was changed and why. Compliance reporting features.

## Testing

### Quick Test

1. Start all services (docker-compose, backend, frontend)
2. Open browser to http://localhost:5173
3. Click "Anonymize from FHIR" button
4. Watch workflow panel show tool calls and AI decisions
5. View results in comparison tab

### Test with Different Formats

Upload FHIR JSON file from Synthea output. Upload generic JSON with patient data. Upload text file with patient information. AI should detect PII in all formats.

### Verify PII Detection

Check workflow shows both mandatory and AI detected fields. Verify all sensitive data removed from results. Confirm medical data preserved.

## Troubleshooting

### Backend Won't Start

Check Python dependencies installed. Verify .env file has GEMINI_API_KEY. Ensure port 5000 not in use.

### Frontend Won't Connect

Check backend running on port 5000. Verify CORS settings allow localhost:5173. Check browser console for errors.

### MCP Tools Not Showing

Restart backend to register tool callback. Check MCP server running on port 8000. Verify docker-compose services are up.

### No Patients in FHIR

Run upload_patients.py script. Generate data with Synthea first. Check FHIR server at http://localhost:8080

### AI Detection Not Working

Verify GEMINI_API_KEY is valid. Check network connection. Look for errors in backend console. AI might return empty list if data unclear.
