# Workspace Triage Demo - How to Run

## What this tests

Two chained autonomous workspaces:

1. **ROI workspace** - receives pathology crops, runs cell segmentation, routes images to CELLPOSE/normal or CELLPOSE/urgent based on cell count
2. **CELLPOSE workspace** - receives routed images, generates clinical reports and sends urgent findings to the FHIR server

## Prerequisites

- Docker stack running (`docker compose up`)
- Cellpose MCP server enabled in Settings
- FHIR MCP server running locally and connected via HTTP

### Start the FHIR server (separate terminal, from fhir-mcp-server/)

```bash
source venv/bin/activate
fhir-mcp-server
```

### Connect the FHIR server in the UI (Settings > Add MCP Server)

- Name: `fhir`
- URL: `http://host.docker.internal:8001/mcp`
- Type: HTTP

### Create the workspaces in the UI (Settings > Workspaces)

**ROI workspace**
- Watched path: `/app/workspaces/ROI`
- Prompt: paste ROI line from prompts.txt

**CELLPOSE workspace**
- Watched path: `/app/workspaces/CELLPOSE`
- Prompt: paste CELLPOSE line from prompts.txt

## Run the simulator

From this folder (simulator/), with dependencies installed:

```bash
pip install -r requirements.txt
python server.py --watch-dir ../orchestrator/workspaces/ROI --sample ROI_TEST_IMAGE.jpeg
```

## Trigger image delivery

In a separate terminal:

```bash
curl -X POST "http://localhost:7100/send-sample?n=5"
```

This drops 5 random crops of the sample image into the ROI watched folder. Each crop has a different size so cell counts will vary naturally.

## Notes

- The ROI agent creates the `normal/` and `urgent/` subfolders inside `/app/workspaces/CELLPOSE/` automatically if they do not exist yet.

## Expected flow

1. ROI agent runs cellpose on each image
2. Images with fewer than 1000 cells go to `/app/workspaces/CELLPOSE/normal/`
3. Images with 1000 or more cells go to `/app/workspaces/CELLPOSE/urgent/`
4. A triage log is written to the ROI workspace
5. CELLPOSE agent picks up urgent images and for each one: creates an anonymous Patient on FHIR (identified only by filename), then creates a linked Observation recording the high cell density finding

## Check FHIR results

Browse created Observations at:
https://hapi.fhir.org/baseR4/Observation?_pretty=true
