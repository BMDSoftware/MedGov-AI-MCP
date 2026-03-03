# Running AgenticHealthMCP

## Requirements

- Python 3.11+
- Node.js 18+
- A Gemini API key (get one free at https://aistudio.google.com/app/apikey) **or** a local [Ollama](https://ollama.com) instance
- GPU recommended for MONAI inference (CPU works but is slow)

---

## Quick start

If you just want to get it running, fill in your credentials in `orchestrator/.env` (copy from `orchestrator/.env.example` first) and then run:

```bash
./run.sh
```

The script will handle all setup steps below automatically.

---

## Manual setup

## 1. Set up each MCP server

Each MCP server has its own Python virtual environment. Run the following from the repo root:

```bash
# MONAI imaging server
cd mcp-monai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# RadLex / RadReport server
cd mcp-radlex
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# DICOM utilities server
cd mcp-utils
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Skills server
cd mcp-skills
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..
```

---

## 2. Set up the orchestrator

```bash
cd orchestrator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..
```

---

## 3. Configure environment variables

```bash
cd orchestrator
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `LLM_BACKEND` | `gemini` (cloud) or `ollama` (local) |
| `GEMINI_API_KEY` | Your Gemini API key (if using Gemini) |
| `GEMINI_MODEL` | Model name, e.g. `gemini-2.0-flash` |
| `OLLAMA_URL` | Ollama base URL, e.g. `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name, e.g. `llama3.1:8b` |
| `APP_ROOT` | Absolute path to the repo root, e.g. `/home/user/AgenticHealthMCP` |

```bash
cd ..
```

---

## 4. Configure MCP server paths

```bash
cd orchestrator
cp mcp-config.json.example mcp-config.json
```

The config uses `${APP_ROOT}` which is automatically expanded from your `.env` at startup — no further edits needed as long as `APP_ROOT` is set correctly.

```bash
cd ..
```

---

## 5. Set up the frontend

```bash
cd frontend
npm install
cd ..
```

---

## 6. Run the application

Open two terminals:

**Terminal 1 — Backend:**
```bash
cd orchestrator
source venv/bin/activate
python backend.py
```

The API will be available at `http://localhost:5001`.
Swagger UI (API docs) available at `http://localhost:5001/docs`.

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

The UI will be available at `http://localhost:5173`.

---

## Notes

- The first time you run inference, MONAI will download the selected model bundle from the MONAI Model Zoo. This requires an internet connection and may take a few minutes depending on the model size.
- The FHIR server is optional. If not configured, the patients list falls back to mock data.
- All uploaded files and session data are stored in `orchestrator/data/`.
- To reset all sessions and uploaded data, delete the contents of `orchestrator/data/uploads/` and `orchestrator/data/health.db`.
