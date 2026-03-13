# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MedGov-AI-MCP is a multi-agent orchestrator for healthcare AI. It coordinates LLM reasoning (Gemini/Ollama), medical image analysis (MONAI), and radiology reporting (RadLex) through a Model Context Protocol (MCP) server ecosystem, with a React frontend.

## Development Commands

### Bootstrap (recommended for fresh setup)
```bash
./run.sh
```
This auto-creates venvs for all Python modules, fills `.env` from `.env.example`, installs frontend deps, and starts both servers.

### Running manually
```bash
# Backend (Port 5001)
cd orchestrator && source .venv/bin/activate && uvicorn backend:app --host 0.0.0.0 --port 5001 --reload

# Frontend (Port 5173)
cd frontend && npm run dev
```

### Linting
```bash
# Python (ruff)
ruff check orchestrator/ mcp-monai/ mcp-radlex/ mcp-utils/ mcp-skills/

# Frontend
cd frontend && npm run lint
```

### Docker
```bash
docker-compose up                                # GPU variant
docker-compose -f docker-compose.cpu.yml up     # CPU-only
```

### Python requirements
- Python >=3.12, <3.13 (strict requirement in `pyproject.toml`)
- Each module (orchestrator, mcp-monai, mcp-radlex, mcp-utils, mcp-skills) has its own isolated venv and `requirements.txt`

## Architecture

### Backend (orchestrator/)

The orchestrator is a FastAPI app (`backend.py`, port 5001) that wires together:

- **`agenticAgent.py`** — Core decision engine. Runs an agentic loop: loads patient memory, calls Gemini/Ollama with available tools, executes tool calls via MCP, iterates until a final answer. Supports "debug" mode (raw technical output) and "normal" mode (clinical language for physicians).
- **`gemini_client.py`** / **`ollama_client.py`** — Stateless LLM clients. Each query gets a fresh conversation. `gemini_client.py` converts MCP tool schemas into Gemini's format.
- **`tool_registry.py`** — Reads `mcp-config.json`, launches MCP server subprocesses (stdio transport) or connects to HTTP MCP servers, and discovers all available tools.
- **`task_runner.py`** — Background task queue using `ThreadPoolExecutor` (4 workers). Long-running ops (MONAI inference, report generation) run here. Each task gets a fresh MCP session. Results are persisted to SQLite and pushed to frontend via SSE (`GET /api/events`).
- **`database.py`** — SQLite persistence (`data/health.db`). Tables: `sessions`, `session_context`, `uploaded_files`, `background_tasks`.
- **`sessionContext.py`** — Manages per-session tool call history and metadata.

### MCP Server Ecosystem

Five MCP servers, each with its own venv, are launched as subprocesses by the orchestrator:

| Server | Purpose |
|---|---|
| `mcp-monai/` | MONAI medical image inference (CT/MRI segmentation) |
| `mcp-radlex/` | RadReport template fetch & fill (RSNA API) |
| `mcp-utils/` | DICOM metadata extraction and file utilities |
| `mcp-skills/` | Discovers and activates skill definitions from `orchestrator/skills/` |
| `fhir-mcp-server/` | FHIR/HL7 integration (optional, HTTP transport) |

### Skills System

`orchestrator/skills/` contains reference skill definitions (not code plugins). Each skill directory has:
- `SKILL.md` — Instructions injected into the agent's system prompt
- `references/` — Schemas, templates, clinical prompts
- `scripts/` — Utility scripts

Current skills: `monai-inference`, `radiology-workflow-sequencer`, `clinical-reports`, `pydicom`.

### Frontend (frontend/)

React 18 + Vite SPA. Communicates with the backend REST API and SSE stream. Key components: `AutonomousAgent.jsx`, `PatientSelection.jsx`, `Sessions.jsx`, `Results.jsx`, `InferenceTest.jsx`. API base URL configured in `src/config.js`.

## Configuration

### `orchestrator/.env`
```
LLM_BACKEND=gemini           # or "ollama"
GEMINI_API_KEY=<key>
GEMINI_MODEL=gemini-2.0-flash
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
APP_ROOT=/absolute/path/to/repo   # auto-set by run.sh
```

### `orchestrator/mcp-config.json`
Defines MCP servers. Uses `${APP_ROOT}` substitution (expanded at startup from `.env`). Copy from `mcp-config.json.example` to get started.

## Key API Endpoints

- `POST /api/process-query` — Main agent query
- `POST /api/upload` — Upload medical image file
- `GET /api/sessions` / `POST /api/sessions` — Session management
- `GET /api/events` — SSE stream for background task updates
- `POST /api/monai/infer` — Direct MONAI inference (bypasses agent)
- `GET /docs` — Swagger UI

## Current Branch State

`feature/mem0` integrates mem0.ai + ChromaDB for persistent patient memory. Per commit history, this is **in-progress and has known issues**. Modified files: `agenticAgent.py`, `gemini_client.py`, `uv.lock`. The `main` branch is the stable baseline.

## Ruff Configuration

Line length 120. Rules E, F enabled; E501 ignored. `backend.py` additionally ignores E402.
