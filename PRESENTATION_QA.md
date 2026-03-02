# Presentation Q&A — Technical Terms & Likely Questions

---

## High Probability Questions

**"How does MCP actually work — how does the agent call a tool?"**

Each MCP server is a subprocess launched via `stdio` transport. The orchestrator opens a persistent session to each server using the MCP Python SDK (`AsyncExitStack` + `ClientSession`). When the LLM decides to call `monai.analyze_image`, the agent:
1. Looks up which server owns that tool (tool registry maps `monai.*` → monai session)
2. Calls `session.call_tool(tool_name, arguments)` over stdio JSON-RPC
3. Gets back a structured result and feeds it to Gemini as a function response

**"Why stdio and not HTTP?"**

Stdio is the simplest MCP transport — the server is a child process, communication is stdin/stdout pipes. It avoids networking overhead and port management. HTTP/SSE transport exists in MCP for remote servers, which we'd need if the MONAI server ran on a GPU machine elsewhere.

**"How does Gemini know what tools exist?"**

At startup, `tool_registry.py` calls `session.list_tools()` on each MCP server. The returned tool schemas (JSON Schema) are converted to Gemini `FunctionDeclaration` objects and passed in `GenerateContentConfig`. Gemini sees the tool names, descriptions, and parameter schemas — it decides when to call them based on the conversation.

**"What is the three-phase loop and why was it needed?"**

Gemini can return multiple function calls in a single response turn (e.g., it decides to call `analyze_image` on three files at once). The Gemini API requires that you respond with exactly N function results for N calls, all in one `send_message` call. If you confirm tools one at a time (one result per message), the count mismatches and Gemini throws an error. The three-phase loop fixes this: collect all calls first, execute them all, send all results together.

**"What is the system prompt doing and how does it change in normal mode?"**

The system prompt sets the agent's behavior rules — what tools to call, how to handle files, the multi-file rule, background task rules. In normal mode, an additional block (`NORMAL_MODE_COMMUNICATION_RULES`) is appended to the base prompt instructing the AI to respond in clinical language without exposing technical details. This is injected via `set_mode_extension()` which calls `update_tools()` to rebuild the `GenerateContentConfig` and restart the chat session.

**"How do background tasks work without blocking the conversation?"**

When `run_inference` is called, the agent intercepts it (it's treated as a built-in), submits it to a `ThreadPoolExecutor` via `task_runner.submit_task()`, and immediately returns a "task queued" response to Gemini. The inference runs in a background thread. When it finishes, the thread pushes an SSE event to an `asyncio.Queue`, which the `/api/events` endpoint streams to the frontend as a notification.

**"What is SSE and why not WebSockets?"**

Server-Sent Events is a one-way push channel from server to browser over a normal HTTP connection. The frontend opens `EventSource('/api/events')` and receives JSON events (`task_queued`, `task_running`, `task_done`, `task_failed`). WebSockets are bidirectional, which is more complex to implement. Since the server only needs to push task status updates (no client-to-server data on that channel), SSE is simpler and sufficient.

**"What does session context do?"**

`SessionContext` accumulates structured facts extracted from tool results during a conversation — modality, body part, patient data, model used. Before each query, this context is injected into the prompt so Gemini doesn't need to re-call `analyze_image` or `parse_dicom` to remember what was already discovered. It clears on session reset.

---

## Medium Probability Questions

**"Why did you choose Gemini over GPT or Claude?"**

Gemini 2.0 Flash has native multi-modal support (images + text), good function calling, and is free-tier accessible. The code also supports Ollama as a local alternative with the same interface (OllamaResponse wrapper classes mirror Gemini's response format). The architecture is LLM-agnostic by design.

**"What is the difference between skills and direct MCP tools?"**

Direct MCP tools are one function call — `utils.parse_dicom` returns DICOM metadata immediately. Skills require 3–4 calls: read the skill file, optionally read references, then execute a script. For existing tasks with a dedicated MCP tool, skills are slower and the LLM prefers MCP anyway. Skills are valuable as a scaling mechanism: when you have too many domain protocols to fit in the system prompt, you lazy-load them on demand.

**"How does the MONAI inference pipeline work?"**

`mcp-monai/server.py` receives a file path and model name. It loads the MONAI bundle from disk (pre-downloaded from MONAI Model Zoo), runs the inference transform pipeline on the input volume, and returns segmentation metadata (structures found, volumes). The actual PyTorch inference runs on GPU if available. The result is a dictionary of anatomical structures with their segmented volumes in mm³.

**"How do you handle DICOM series (directories) vs single files?"**

At upload time, directories are tagged with `file_type='dicom_dir'` in the database. In the prompt sent to Gemini, directory paths appear with the prefix `[DICOM SERIES DIR]` so the model knows to treat them as 3D volumes. In `gemini_client.py`, directories are skipped when trying to send images to Gemini (you can't send a folder as an image). MONAI handles the directory natively — it reads and stacks all `.dcm` slices into a 3D tensor automatically.

**"What is AsyncExitStack and why one per server?"**

`AsyncExitStack` is Python's async context manager for managing multiple async resources. Each MCP server session needs to be opened and closed cleanly. Initially all servers shared one stack — if one failed (e.g. FHIR), it cancelled the entire stack including working servers. The fix was one stack per server: each server opens and closes independently, a failed server only tears down its own stack, others continue working.

**"What happens when a tool fails?"**

The agent catches the exception, records the failure in the DB as `status='failed'` with the error message, and prompts Gemini with the error text so it can explain what happened in plain language. There's also a `_explain_inference_error()` function that asks the LLM to generate a human-readable explanation of the technical error, which appears in the Results tab.

---

## Lower Probability but Worth Knowing

- **Why SQLite?** Single-machine deployment, no setup, enough for one concurrent user. PostgreSQL when scaling to multi-user.
- **What is `task.uncancel()`?** Python 3.11 feature. When a coroutine is cancelled via `CancelledError` but you want to handle it gracefully and continue, you call `task.uncancel()` to decrement the cancellation count and allow the task to keep running.
- **How does the frontend know which session's tasks to show?** Every task is stored with a `session_id` in the DB. The frontend passes `currentSessionId` as a query param to `/api/tasks`, which filters by session. Same for the Report tab.
- **Why is the three-phase loop also needed during tool confirmation?** In debug mode, when you confirm one tool from a multi-call turn, the `confirm_tool_execution` function chains through the remaining calls in `turn_remaining_calls`, accumulates all results, and only sends them to Gemini after all confirmations are processed. Same constraint — Gemini needs all N results at once.
