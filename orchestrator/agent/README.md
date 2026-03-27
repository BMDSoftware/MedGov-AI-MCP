# Agent Package

The `agent/` package contains the orchestration agent that decides which MCP tools to call based on user goals and context. It was refactored from a single monolithic file into focused modules using mixin composition.

## Architecture

`AgenticAgent` is assembled from multiple mixin classes, each in its own file. The main class in `core.py` inherits from all mixins, combining their methods into a single cohesive agent. No mixin imports another mixin — they all access shared state (`self.tool_registry`, `self.llm_client`, `self.session_context`, etc.) set up in `AgenticAgent.__init__`.

```
core.py (AgenticAgent)
  ├── tool_management.py  (ToolManagementMixin)
  ├── session.py          (SessionMixin)
  ├── skills.py           (SkillsMixin)
  ├── confirmation.py     (ConfirmationMixin)
  ├── execution.py        (ExecutionMixin)
  └── formatting.py       (ResultFormattingMixin)
```

Shared data modules (`constants.py`, `prompts.py`, `builtin_tools.py`) are imported by the mixins but never import from them, ensuring a one-directional dependency flow with no circular imports.

## Files

### `__init__.py`
Package entry point. Exports `AgenticAgent` so consumers can write `from agent import AgenticAgent`.

### `constants.py`
Module-level configuration values:
- `LLM_BACKEND` — which LLM provider to use (`"ollama"` or `"gemini"`), read from the `LLM_BACKEND` env var.
- `SKILL_DIR_PATH` — filesystem path to the `skills/` directory.
- `_DISABLED_TOOLS_FILE` — path to the disabled tools JSON (legacy, currently unused).

### `prompts.py`
All prompt template strings used by the agent:
- `NORMAL_MODE_COMMUNICATION_RULES` — instructions for clinical/professional response style in normal mode.
- `PATIENT_FOCUS_PROMPT_TEMPLATE` — system prompt template with `{patient_id}` and `{patient_name}` placeholders. Defines tool usage rules, background task rules, and conversation rules for patient-focused sessions.
- `FIRST_ITERATION_PROMPT_TEMPLATE` — the initial prompt sent to the LLM on the first iteration of a task, includes goal, data context, file list, and session history.
- `EVAL_PROMPT_TEMPLATE` — the follow-up prompt sent after tool execution, asking the LLM whether the goal is achieved or what to do next.

### `builtin_tools.py`
Contains the `BUILTIN_TOOLS` dictionary (schemas for `queue_task`, `list_tasks`, `goal_achieved`, `need_more_info`) and shared handler functions that are called from both the execution loop and the confirmation flow:
- `handle_list_tasks(session_id)` — queries the DB for background tasks and returns a summary.
- `handle_queue_task(session_id, arguments)` — submits a new background task via `task_runner`.
- `handle_inference_as_task(session_id, arguments, session_context_entries, inference_queued)` — queues a `monai.run_inference` call as a background task, pulling body part/modality from session context.
- `save_radlex_report(session_id, tool_name, result, arguments)` — persists a RadLex report to the DB so it appears in the Report tab.

These shared functions eliminate duplicated logic that previously existed in both `execute_task` and `confirm_tool_execution`.

### `tool_management.py`
`ToolManagementMixin` — manages the set of available and enabled tools:
- `enable_tool` / `disable_tool` — toggle individual tools on or off.
- `refresh_server_tools` — re-discover tools from a specific MCP server.
- `add_mcp_server` / `remove_mcp_server` — dynamically add or remove MCP server connections.
- `refresh_available_tools` — reload config and re-discover all tools.
- `_refresh_agent_components` — pushes the current enabled tool set to the LLM client.

### `session.py`
`SessionMixin` — patient focus and session context persistence:
- `set_patient_focus(patient_id, patient_name)` — configures the LLM system prompt for a specific patient using the template from `prompts.py`.
- `reset_session_context` / `save_context_to_db` / `load_context_from_db` — manage session context lifecycle and DB persistence.
- `_record_and_persist` — records a tool result to in-memory context and optionally persists to DB.
- `_extract_key_data` — extracts clinically relevant facts (modality, body part, patient info, etc.) from tool results for cross-query memory.

### `skills.py`
`SkillsMixin` — loads skill metadata:
- `load_all_skills` — scans the `skills/` directory for `SKILL.md` files, parses their YAML frontmatter, and returns a formatted text listing for the system prompt.

### `confirmation.py`
`ConfirmationMixin` — handles the tool confirmation workflow (debug mode):
- `confirm_tool_execution(session_id)` — executes a pending tool after user approval, drains any built-in tools in the queue, then resumes the task loop.
- `_drain_builtin_calls` — processes built-in tools (list_tasks, queue_task, inference) at the front of a remaining-calls queue without requiring confirmation.
- `deny_tool_execution` — cancels a pending tool call.
- `get_pending_tool` — returns the current pending tool call details.

### `execution.py`
`ExecutionMixin` — the core agentic loop, broken into sub-methods:
- `execute_task(goal, data, fileList, ...)` — the main loop that iterates up to `max_iterations`, prompting the LLM and processing tool calls each iteration.
- `_build_prompt(goal, data, fileList, execution_history, is_gemini)` — constructs the prompt string and extracts 2D images to send to the LLM. Handles first-iteration vs. follow-up prompt templates.
- `_parse_llm_response(response)` — scans LLM response parts for text content and function calls, resolves tool name prefixes.
- `_handle_text_signals(...)` — detects text-based fallbacks for `GOAL_ACHIEVED` and `NEED_MORE_INFO` when the LLM doesn't use the proper tool call.
- `_process_tool_calls(turn_calls, ...)` — processes each function call: intercepts built-in tools, handles confirmation flow, executes MCP tools, records results, and persists failed tasks to DB.
- `_send_turn_results_to_llm(turn_results)` — sends accumulated tool results back to the LLM in a single message (Gemini optimization).

### `formatting.py`
`ResultFormattingMixin` — human-readable result formatting:
- `_create_result_summary(tool_name, result)` — generates a short summary string for a tool result (e.g., `"Image analyzed: CT, shape [512, 512, 128]"`). Handles MONAI, RadLex, FHIR, and DICOM tools with specific formatting, plus a generic fallback.
- `_extract_answer_from_results(agent_response, execution_history, final_result)` — builds a detailed answer from the agent's text response and the execution history, formatting model lists, search results, and template listings.

### `core.py`
The `AgenticAgent` class itself. Inherits from all six mixins and defines:
- `__init__` — initializes all shared state (tool registry, LLM client, session context, logger, mode flags).
- `_initialize_components` — async setup that discovers tools, loads skills, and creates the LLM client (Ollama or Gemini).
- `close` — async cleanup for tool registry resources.
- `set_mode(mode)` — switches between `"debug"` (confirmation required) and `"normal"` (auto-execute with clinical communication style).
- `set_agent_type(autonomous)` — toggles autonomous execution mode.
