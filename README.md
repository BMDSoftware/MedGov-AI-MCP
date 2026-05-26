# MedGov-AI

An agentic AI platform for clinical imaging orchestration. MedGov-AI connects a reasoning agent to medical AI tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), enabling autonomous multi-step clinical workflows from a natural language interface.

## What it does

- **Autonomous analysis** - Upload DICOM series or pathology images and describe what you want. The agent selects tools, runs inference, and produces a structured clinical report without manual intervention.
- **Segmentation and cell detection** - MONAI models for volumetric organ segmentation on CT/MRI; Cellpose v4 for cell detection and counting on pathology ROI images.
- **Structured report generation** - RadLex/RadReport templates for radiology; pathology-specific templates for whole-slide image analysis.
- **Workspace monitoring** - Register a directory as a workspace. When files arrive (e.g. from a PACS or scanner), the agent automatically analyses them and writes results to the configured output folder.
- **Skills** - Plain-text workflow protocols that guide the agent through domain-specific clinical sequences, improving reliability and reducing incorrect tool use.
- **Background tasks** - Inference jobs run in the background with real-time progress streamed to the UI via SSE.
- **iPath integration** - Connects to the iPath telepathology platform for whole-slide image retrieval and ROI analysis.

## Architecture

```
┌──────────────────────────────────┐
│           React Frontend         │
│  (Upload · Analysis · Results ·  │
│   Reports · Workspaces)          │
└────────────────┬─────────────────┘
                 │ REST + SSE
┌────────────────▼─────────────────┐
│        FastAPI Orchestrator      │
│  Agent (Gemini / Ollama) ·       │
│  Task runner · Watcher service   │
└──┬───────┬──────┬────┬───────┬───┘
   │       │      │    │       │   MCP (stdio/HTTP)
┌──▼──┐ ┌──▼──┐ ┌─▼─┐ ┌▼────┐ ┌▼──────┐
│monai│ │radlex│ │cell│ │ipath│ │skills │
│     │ │      │ │pose│ │     │ │+utils │
└─────┘ └──────┘ └───┘ └─────┘ └───────┘
```

## Quick start

**Requirements:** Python 3.11+, Node.js 18+, a Gemini API key or local Ollama instance. GPU recommended for inference.

```bash
# 1. Copy and fill in your credentials
cp orchestrator/.env.example orchestrator/.env
# edit orchestrator/.env: set LLM_BACKEND, GEMINI_API_KEY, APP_ROOT

# 2. Run everything
./run.sh
```

The script sets up all virtual environments, installs dependencies, and starts the backend and frontend.

- UI: http://localhost:5173
- API: http://localhost:5001
- API docs: http://localhost:5001/docs

See [RUN.md](RUN.md) for manual setup, Docker deployment, and configuration details.

## MCP Servers

| Server | Function |
|---|---|
| `mcp-monai` | Volumetric segmentation and organ analysis via MONAI |
| `mcp-radlex` | Structured radiology report generation using RadLex templates |
| `mcp-cellpose` | Cell detection and counting on pathology ROI images |
| `mcp-ipath` | Whole-slide image retrieval from iPath telepathology platform |
| `mcp-utils` | DICOM parsing, metadata extraction, file utilities |
| `mcp-skills` | Skill file loading for domain-specific workflow guidance |

## Acknowledgements

This work has received support from the "Health from Portugal - Agenda Mobilizadora para a Inovação Empresarial" project, funded by Plano de Recuperação e Resiliência português under grant agreement No C644937233-00000047.

## License

TBD
