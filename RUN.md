# Running MedGov-AI

## Requirements

- Docker and Docker Compose
- A Gemini API key (get one free at https://aistudio.google.com/app/apikey) **or** a local [Ollama](https://ollama.com) instance
- For GPU inference: an NVIDIA GPU with the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed

---

## 1. Configure environment

```bash
cp orchestrator/.env.example orchestrator/.env
```

Edit `orchestrator/.env` and fill in:

| Variable | Description |
|---|---|
| `JWT_SECRET_KEY` | Random secret for signing auth tokens — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `LLM_BACKEND` | `gemini` (cloud) or `ollama` (local) |
| `GEMINI_API_KEY` | Your Gemini API key (if using Gemini) |
| `GEMINI_MODEL` | Model name, e.g. `gemini-2.5-flash` |
| `OLLAMA_URL` | Ollama base URL, e.g. `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name, e.g. `llama3.1:8b` |
| `APP_ROOT` | Absolute path to the repo root, e.g. `/home/user/AgenticHealthMCP` |

---

## 2. Run with Docker Compose

### CPU (default)

Suitable for development and for running without a GPU. MONAI and Cellpose inference will run on CPU — correct but slow for large images.

```bash
docker compose up --build
```

### GPU (NVIDIA)

Requires the NVIDIA Container Toolkit installed on the host. Enables GPU-accelerated inference for MONAI and Cellpose — strongly recommended for the pathology use case.

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml docker compose up --build
```

Or set `COMPOSE_FILE` permanently in your `.env`:

```
COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml
```

Then just run `docker compose up --build`.

Once running:

- UI: http://localhost
- API: http://localhost:5001
- API docs: http://localhost:5001/docs

---

## Alternative: local development (without Docker)

Useful if you want to iterate quickly without rebuilding containers.

**Requirements:** Python 3.11+, Node.js 18+

The quickest way is:

```bash
./run.sh
```

The script creates virtual environments for each MCP server and the orchestrator, installs all dependencies, and starts both the backend and frontend.

Or manually:

### 1. Set up each MCP server

Each MCP server has its own Python virtual environment. Run the following from the repo root:

```bash
# MONAI imaging server
cd mcp-monai && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ..

# RadLex / RadReport server
cd mcp-radlex && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ..

# Cellpose cell detection server
cd mcp-cellpose && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ..

# iPath telepathology server
cd mcp-ipath && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ..

# DICOM utilities server
cd mcp-utils && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ..

# Skills server
cd mcp-skills && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ..
```

### 2. Set up the orchestrator

```bash
cd orchestrator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..
```

### 3. Configure MCP server paths

```bash
cp orchestrator/mcp-config.json.example orchestrator/mcp-config.json
```

The config uses `${APP_ROOT}` which is expanded from your `.env` at startup — no further edits needed as long as `APP_ROOT` is set correctly.

### 4. Set up the frontend

```bash
cd frontend && npm install && cd ..
```

### 5. Run

Open two terminals:

**Terminal 1 - Backend:**
```bash
cd orchestrator
source venv/bin/activate
python backend.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

- UI: http://localhost:5173
- API: http://localhost:5001
- API docs: http://localhost:5001/docs

---

## Notes

- The first time you run inference, MONAI will download the selected model bundle from the MONAI Model Zoo. This requires an internet connection and may take a few minutes.
- All uploaded files, session data, and workspaces are persisted in Docker volumes (`orchestrator/data/` and `orchestrator/workspaces/`).
- To reset all data, stop the containers and delete the contents of `orchestrator/data/` and `orchestrator/workspaces/`.
- The FHIR server is optional. If not configured, it is simply unavailable as a tool.
