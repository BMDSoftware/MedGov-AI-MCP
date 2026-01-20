# Agentic Health Anonymizer

AI-powered medical data anonymization with MCP

## Quick Start

### 1. Start FHIR Infrastructure

```bash
cd fhir-mcp-server
docker-compose up -d
```

Wait 30 seconds for services to start.

### 2. Generate Test Data

```bash
cd synthea
./run_synthea -p 5
```

### 3. Upload Patients to FHIR

```bash
cd poc
python3 upload_patients.py
```

### 4. Start Backend

```bash
cd poc
pip install -r requirements.txt
python3 backend.py
```

### 5. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

### 6. Open Browser

Go to **http://localhost:5173**

Click "Anonymize from FHIR" to test

## Architecture

- Frontend: React (port 5173)
- Backend: FastAPI (port 5000)
- MCP Server: FHIR MCP (port 8000)
- FHIR Server: HAPI FHIR (port 8080)
- AI: Gemini 2.5 Flash

## Features

- Upload any file format (FHIR, JSON, CSV, etc.)
- AI detects and anonymizes PII automatically
- Real-time workflow visualization
- MCP tool calls tracked
- Saves anonymized data to FHIR server
