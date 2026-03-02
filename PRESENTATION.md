# MedGov-AI | Desk Assistance — Presentation Brief

## Title

**MedGov-AI: A Multi-Agent Orchestrator for Healthcare Using the Model Context Protocol**

*Subtitle: Enabling agentic radiology workflows through MCP-native AI orchestration over DICOM, MONAI, and FHIR*

---

## 1. Problem Context (from teacher's plan)

Healthcare systems face three structural problems that motivated this work:

- **Integration complexity**: Clinical teams and IT teams rarely communicate well. Integrating AI tools into existing workflows (PACS, RIS, EHR) requires custom, fragile bridges for every combination. The M×N problem: M hospital applications × N AI services = M×N integrations.
- **LLM auditability**: LLMs are black boxes. In a medical context, you need to know *why* a decision was made and *which tools were called*, especially for audit and compliance.
- **Patient-centric context loss**: LLMs have finite context windows. If the patient's full history isn't always in context, the AI loses coherence across conversations.

The teacher's guiding analogy: the **Language Server Protocol (LSP)** solved M×N for code editors — one protocol, any editor, any language. We propose a similar concept for healthcare: a **Health Agent Assistant Protocol (HAAP)**, one agent layer that talks to any PACS, RIS, EHR, or AI service through MCP.

---

## 2. Objective

Build a **Multi-Agent Orchestrator for healthcare** that:

1. Lets users register and manage MCP services easily
2. Handles any data type (DICOM images, FHIR patient records, clinical notes)
3. Creates actions via natural language (report generation, segmentation, analysis)
4. Keeps the agent patient-centric across a session
5. Audits every LLM action in the patient context

**Use Case 1 (our focus):** A radiologist processes multiple daily exams. MONAI segments organs, RadLex provides report templates, the agent assembles a structured radiology report augmented with patient history.

---

## 3. Key Concepts

| Concept | What it means in this project |
|---|---|
| **MCP (Model Context Protocol)** | Open standard from Anthropic. Lets an LLM call external tools (MONAI, FHIR, RadLex) through a uniform interface — regardless of how each tool works internally |
| **Agentic AI** | The LLM decides which tools to call, in which order, based on context. No hardcoded workflow. |
| **DICOM** | Standard format for medical images. A `.dcm` file can be a single 2D slice or part of a 3D series. |
| **MONAI** | Medical AI framework. Hosts pre-trained models (spleen segmentation, whole-body CT, pancreas, etc.) from MONAI Zoo. |
| **RadLex / RadReport** | Standardized radiology terminology and report templates (ACR standard). |
| **FHIR** | HL7's standard for electronic health records. Lets the agent pull patient demographics, history, and conditions. |
| **SSE (Server-Sent Events)** | Real-time push from backend to frontend without polling. Used for task progress notifications. |
| **Background Task Queue** | Inference runs take 30s–several minutes. The agent queues them in a thread pool and keeps talking to the user while they run. |
| **Session Context** | The agent accumulates structured facts (modality, body part, patient info) across tool calls in the same conversation, so it doesn't re-query tools for data it already has. |

---

## 4. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER (browser)                                │
│  React SPA — Analysis | Results | Report | History | Settings        │
│  Port 5173                                                           │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼───────────────────────────────────────────┐
│                   ORCHESTRATOR  (FastAPI, port 5001)                  │
│                                                                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────┐ │
│  │  backend.py     │  │  agenticAgent.py  │  │  task_runner.py     │ │
│  │  REST endpoints │  │  Three-phase exec │  │  Thread pool        │ │
│  │  File upload    │  │  SessionContext   │  │  Background infer.  │ │
│  │  SSE /events    │  │  Gemini 2.0 Flash │  │  Report generation  │ │
│  └────────┬────────┘  └────────┬─────────┘  └─────────┬───────────┘ │
│           │                   │                       │             │
│  ┌────────▼───────────────────▼───────────────────────▼───────────┐ │
│  │                   tool_registry.py                              │ │
│  │   Per-server AsyncExitStack — discovers & routes tool calls     │ │
│  └─────┬──────────┬──────────────┬────────────┬──────────────┬────┘ │
└────────│──────────│──────────────│────────────│──────────────│───────┘
         │ stdio    │ stdio        │ stdio      │ stdio        │ stdio
┌────────▼──┐  ┌────▼──────┐  ┌──▼───────┐  ┌─▼────────┐  ┌─▼──────┐
│ mcp-monai │  │ mcp-radlex│  │ mcp-utils│  │ mcp-fhir │  │ mcp-   │
│           │  │           │  │          │  │          │  │ skills │
│ Tools:    │  │ Tools:    │  │ Tools:   │  │ Tools:   │  │        │
│ analyze_  │  │ find_     │  │ parse_   │  │ search   │  │ read_  │
│ image     │  │ templates │  │ dicom    │  │ read     │  │ skill  │
│           │  │           │  │          │  │ create   │  │ file   │
│ list_     │  │ get_      │  │ parse_   │  │ update   │  │        │
│ models    │  │ template_ │  │ dicom_   │  │ delete   │  │ exec_  │
│           │  │ schema    │  │ directory│  │          │  │ script │
│ run_      │  │           │  │          │  │          │  │        │
│ inference │  │ generate_ │  │          │  │          │  │        │
│           │  │ report    │  │          │  │          │  │        │
│ Models:   │  └───────────┘  └──────────┘  └──────────┘  └────────┘
│ spleen_ct │
│ wholeBody │       ┌───────────────────────────────────┐
│ pancreas_ │       │         SQLite Database            │
│ ct_dints  │       │  sessions | uploaded_files         │
│ liver_    │       │  background_tasks | results        │
│ tumor_ct  │       └───────────────────────────────────┘
│ swin_unetr│
│ (broken)  │
└───────────┘
```

**Flow: User uploads DICOM → asks for inference:**
```
User types query
      │
      ▼
backend.py  (/api/process-query)
      │
      ▼
agenticAgent.execute_task()
  ├─ Phase 1: Gemini 2.0 Flash sees tools + IMAGES AVAILABLE context
  │           Returns function calls for this turn
  ├─ Phase 2: For each call:
  │   ├─ built-ins (queue_task, list_tasks) → execute immediately
  │   └─ MCP tools → debug: ask confirmation / normal: execute directly
  └─ Phase 3: send ALL results in one send_multiple_function_responses()
                    │
                    ▼
           Gemini decides next action
                    │
         ┌──────────┴─────────────┐
         │                        │
   More tool calls           "GOAL_ACHIEVED"
   (repeat phases)                │
                                  ▼
                         task_runner.submit_task()
                         (background thread)
                                  │
                         SSE event → frontend toast
                                  │
                         Results tab updated
```

---

## 5. Skills System — Approach & Limitations

### Concept
The **agent skills system** (mcp-skills) was inspired by how you avoid stuffing all domain knowledge into the system prompt at once. Instead:

1. The LLM sees only a directory of skill names + short descriptions
2. When it needs a skill, it calls `skills.read_skill_file(name)` to load the full `SKILL.md` (e.g. pydicom documentation, clinical report standards, HIPAA checklist)
3. If it needs more detail, it calls `skills.read_references(name, file)` for reference material
4. Then executes the actual work via `skills.execute_script()` or existing MCP tools

### The Limitation We Found (critical for presentation)

**Skills add 3–4 tool calls per task, where a direct MCP tool does it in 1.**

For example, to extract DICOM metadata:
- **Skill path**: `read_skill_file` → `read_references` → `execute_script(extract_metadata.py)` = 3 calls, seconds of latency
- **Direct MCP path**: `utils.parse_dicom` = 1 call, result immediate

Because Gemini prefers the most direct path, it will almost always use the MCP tool directly and ignore skills — unless explicitly instructed to use skills first in the system prompt, and even then it's inconsistent.

**Where skills DO make sense:**
- When there is NO direct MCP tool for the task
- When context window scaling is needed (too many skills to fit all instructions at once, lazy-load them)
- For documenting workflows and protocols (clinical report standards, anonymization rules)

**Conclusion reached:** For the current use case, direct MCP tools (mcp-monai, mcp-radlex, mcp-utils) are more reliable and efficient than the skills wrapper. Skills are valuable as a *scaling mechanism for knowledge*, not for replacing tool calls.

---

## 6. Frontend — Approach & Vision

### Starting point
The initial prototype was a simple file-upload page with a drag-and-drop, a "workflow panel" showing raw tool calls and AI thinking, and a results display. Pure developer tooling.

### Evolution
Over the course of the project, the frontend evolved toward a **clinical web application**:

- **Analysis tab**: Chat interface — the clinician types natural language, uploads files/directories, sees responses
- **Results tab**: Background task monitor — all running/completed/failed inferences shown with modality, body part, model used, error explanations
- **Report tab**: Generated radiology reports — both AI-narrative and RadLex template-based
- **History tab**: Session management — load previous sessions, restore chat and uploaded files
- **Settings tab**: Debug/Normal mode toggle, system prompt customization

### Debug vs Normal mode (design decision)
Two audiences needed two modes:
- **Debug mode**: For developers — see every tool confirmation, raw JSON args, internal state. Useful for testing and iteration.
- **Normal mode**: For clinicians — tools run automatically, AI speaks in formal clinical language ("I have submitted the CT abdomen scan for segmentation analysis. Results will appear in the Results tab."), no technical jargon exposed.

### Long-term vision (from meeting notes)
The goal is to evolve this into a **desktop/native application** — not a chat model. The ideal UX is closer to a radiology workstation assistant that runs workflows automatically. Two envisioned scenarios:
1. **Iterative**: Clinician uploads a scan, converses with the agent, analyzes, generates report
2. **Automatic**: Agent watches a directory, re-runs inference automatically when new files appear — no upload needed

---

## 7. Results (What Works Today)

| Feature | Status |
|---|---|
| DICOM upload (single file or full series directory) | Working |
| MONAI segmentation inference (spleen, liver, pancreas, whole-body CT) | Working |
| Multi-file/multi-directory inference auto-queue | Working |
| Background task runner (non-blocking, keeps conversation going) | Working |
| Real-time SSE notifications (toast + badge counter) | Working |
| RadLex report template retrieval + AI-generated narrative | Working |
| Session context accumulation (modality/body part across turns) | Working |
| Session persistence (DB, localStorage, file restore across reloads) | Working |
| Debug/Normal mode toggle with persistence | Working |
| FHIR patient data retrieval | Not working (server fails on startup) |
| SwinUNETR model (`swin_unetr_btcv_segmentation`) | Broken (MONAI API changed) |

---

## 8. Bottlenecks & Known Issues

### Technical bottlenecks

**2D vs 3D model mismatch**
Single `.dcm` slices are 2D arrays [512×512]. MONAI's 3D segmentation models expect volumetric input [D×H×W]. When a single slice is given to a 3D model, the inference crashes with "Sequence must have length 2, got 3." The fix: detect 2D input at the MCP server level and return a structured error before inference starts.

**SwinUNETR model broken**
MONAI changed its SwinUNETR API between versions — the `img_size` parameter was removed. The bundle fails to instantiate, falls back to a generic UNet architecture, then `load_state_dict` fails because the weights are SwinUNETR-shaped. The model is currently unusable.

**Context not persisted across server restarts**
Gemini's chat history (the conversation turns) lives in memory only. Restarting the backend loses the entire conversation. MemZero or a persistent vector store would fix this.

**Multi-call Gemini turn mismatch**
Gemini sometimes returns multiple function calls in a single turn. If the response count to `send_multiple_function_responses` doesn't match exactly, the API errors. This required the three-phase execute_task redesign (collect all calls first, execute, then send all results together).

**FHIR/skills server startup failures**
The FHIR MCP server is not installed/configured on this machine, and the skills MCP server has Mac-specific paths hardcoded. Both fail at startup with `CancelledError`, handled by per-server `AsyncExitStack` isolation.

### Architecture limitations

**LLM is not a perfect planner**
Gemini 2.0 Flash sometimes: stops after analyzing one file instead of all of them; runs the last model from `list_models` instead of the one actually recommended; asks clarifying questions in cases where the system prompt intends it to proceed automatically. Mitigated by system prompt engineering, but a fundamental limit of small/fast models.

**No true multi-user support**
The backend holds session state in global variables and SQLite. One user at a time. A proper deployment would need per-user process isolation.

**Tool redundancy between skills and MCP**
DICOM parsing exists both as `utils.parse_dicom` (MCP, 1 call) and as a pydicom skill (3–4 calls). The agent prefers MCP. Skills are architectural dead weight for current use unless the MCP layer is removed.

---

## 9. Next Steps

**Short term (already planned):**
- Detect 2D DICOM input in mcp-monai and return a clear error before inference
- Fix SwinUNETR bundle by pinning MONAI version or updating bundle config
- Surface failed inference errors in Results tab with AI-generated plain-language explanation
- Add scan metadata hints from directory name / folder path (e.g. a folder named "ChestCT" → modality=CT, bodyPart=chest)

**Medium term:**
- **Cross-session memory (MemZero)**: Agent remembers patient history and conversation across backend restarts
- **Directory watcher**: Automatic mode — watch a path, re-run inference when new files appear, no user interaction needed
- **Segmentation result visualizer**: Overlay segmentation masks on the source DICOM for the clinician
- **Downloadable reports**: Export radiology report as PDF or HL7 FHIR DocumentReference
- **FHIR integration**: Properly deploy and connect the FHIR MCP server for live patient data
- **Data anonymization agent**: Strip PII from DICOM metadata (18 HIPAA identifiers) before upload or sharing — learned from early POC

**Long term / research:**
- **Health Agent Assistant Protocol (HAAP)**: Formalize a protocol spec for M' hospital apps × N' AI services, solving the same M×N problem that LSP solved for code editors
- **Article**: Write up the architecture, the skills vs direct MCP tool comparison, and results
- **Multi-model ensemble**: Run multiple MONAI models and let the agent synthesize combined findings
- **Voice interface**: Clinician speaks, agent processes, speaks results — true hands-free radiology workflow

---

## 10. Key Architectural Decision to Highlight

The **three-phase execute_task redesign** is worth explaining in detail on a slide, because it's a real engineering problem that Gemini introduced:

```
PROBLEM: Gemini can return 3 function calls in one turn.
You must respond with exactly 3 function results, in one message.
If you respond twice (one per confirmation), Gemini errors.

SOLUTION — Three-Phase Loop:
┌─ Phase 1: Collect ─────────────────────────────────────────────┐
│  Scan all parts from Gemini's response.                        │
│  Store ALL function calls in _turn_calls list.                 │
└────────────────────────────────────────────────────────────────┘
┌─ Phase 2: Execute ─────────────────────────────────────────────┐
│  For each call:                                                │
│   • Built-in (queue_task, list_tasks) → run immediately        │
│   • MCP tool → confirm (debug) or run (normal)                 │
│  Accumulate all results in _turn_accumulated_results.          │
└────────────────────────────────────────────────────────────────┘
┌─ Phase 3: Flush ───────────────────────────────────────────────┐
│  After ALL calls in the turn are processed:                    │
│  send_multiple_function_responses([result1, result2, result3]) │
│  Gemini gets exactly N results for N calls. No mismatch.       │
└────────────────────────────────────────────────────────────────┘
```

---

## Suggested Slide Structure

1. **Title** — MedGov-AI | Desk Assistance
2. **Problem** — M×N integration, LLM auditability, patient-centric context loss
3. **Proposed Solution** — HAAP analogy (LSP → ACP → HAAP), MCP as the unifying layer
4. **Use Case 1** — Radiologist workflow: DICOM → MONAI → RadLex → Report
5. **Architecture Diagram** — The ASCII diagram above, simplified
6. **MCP Servers** — Table: server, tools, what it connects to
7. **Agentic Loop** — Three-phase execute_task diagram
8. **Skills vs Direct MCP Tools** — Side-by-side comparison, trade-offs
9. **Frontend Evolution** — Screenshots / description from debug tool to clinical app
10. **Debug vs Normal Mode** — What each mode looks like
11. **Results** — What works, what doesn't (table above)
12. **Bottlenecks** — 2D/3D mismatch, SwinUNETR, context loss, LLM planning limits
13. **Next Steps** — Short/medium/long term roadmap
14. **Conclusion** — What MCP enables for healthcare AI integration
