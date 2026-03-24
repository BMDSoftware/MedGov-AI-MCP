#!/usr/bin/env python3
import os
import json
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from datetime import datetime
import logging

import yaml

from tool_registry import ToolRegistry
from sessionContext import SessionContext
from logger import Logger
import task_runner
import database as db


# LLM Backend selection: "ollama" (local) or "gemini" (API)
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")

SKILL_DIR_PATH = Path(__file__).parent / "skills"

NORMAL_MODE_COMMUNICATION_RULES = """COMMUNICATION STYLE — NORMAL MODE:

You are communicating with medical professionals (physicians, radiologists, clinicians). Your workflow and decision-making are unchanged from normal operation. The only difference is how you communicate results.

1. Use formal, professional language appropriate for a clinical environment.
2. NEVER expose raw JSON, file paths, tool names, model identifiers, or internal technical parameters in your responses.
3. When inference has been queued say: "I have submitted the [anatomy/modality] scan for analysis. Results will appear in the Results tab when complete."
4. When scan metadata is extracted say: "I have reviewed the scan. This appears to be a [modality] examination of the [body part]."
5. When listing models or results, describe them by their clinical application, not their technical identifiers.
6. When something fails, explain it in plain clinical language and suggest what the user should do next.
7. Keep responses to 2–4 sentences unless more clinical detail is genuinely needed.
8. Do not narrate your internal process or the tools you called — only state the outcome to the user."""

class AgenticAgent:
    """AI agent that decides which MCP tools to call based on context and data"""

    _DISABLED_TOOLS_FILE = Path(__file__).parent / "data" / "disabled_tools.json"

    def __init__(self, callback=None, enable_debug_logging=True, log_level=logging.DEBUG):
        self.tool_registry = ToolRegistry()
        self.available_tools = {}
        self.agent_tools: Set[str] = set()
        self.callback = callback  # Callback function for real-time event tracking
        self.llm_client = None
        self.session_context = SessionContext()  # Persists tool results across queries
        self.mode = 'debug'  # 'debug' or 'normal'
        self.is_agent_autonomous = False  # Whether the agent is currently executing autonomously
        self.require_confirmation = True  # Require user confirmation before tool execution
        self.pending_tool_call = None  # Stores tool call waiting for confirmation
        self.pending_task_context = None  # Stores context for resuming after confirmation
        
        # Setup debug logging using Logger class
        self.logger = Logger(name="AgenticAgent", log_level=log_level, is_active=enable_debug_logging)
        
        # Use async init pattern for tool discovery
        # You must call await self._initialize_components() after instantiation

    # Built-in tool schema for queue_task - registered alongside MCP tools so the
    # LLM knows it can call it. Execution is handled locally (never goes to MCP).
    BUILTIN_TOOLS = {
        "queue_task": {
            "description": (
                "Queue a long-running operation as a background task. "
                "Use this instead of calling a tool directly whenever the operation may take more than a few seconds "
                "(e.g. MONAI inference, report generation, bulk analysis). "
                "The function returns immediately so you can keep talking to the user. "
                "The user will receive a notification when the task finishes."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "task_type": {
                        "type": "string",
                        "description": "Category of the task. Use 'inference' for MONAI model runs, 'report' for report generation, or any descriptive string for other tasks.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable label shown in the Results tab, e.g. 'WholeBody segmentation on PANCREAS_0001'.",
                    },
                    "input_data": {
                        "type": "object",
                        "description": "Task-specific inputs as a JSON object. For 'inference': {image_path, model_name}. For 'report': {task_ids, patient_context}.",
                    },
                },
                "required": ["task_type", "description", "input_data"],
            },
            "server": "__builtin__",
            "original_name": "queue_task",
            "transport": "builtin",
        },
        "list_tasks": {
            "description": (
                "List all background tasks for the current session and their status. "
                "Use this when the user asks whether their inference or report tasks have finished, "
                "or to check how many tasks are still running."
            ),
            "schema": {
                "type": "object",
                "properties": {},
            },
            "server": "__builtin__",
            "original_name": "list_tasks",
            "transport": "builtin",
        },
        "goal_achieved": {
            "description": (
                "Call this tool when you have completed the user's goal or answered their question. "
                "You MUST call this tool to signal completion — do not just say 'done' in text."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Final answer or summary of what was accomplished.",
                    },
                },
                "required": ["summary"],
            },
            "server": "__builtin__",
            "original_name": "goal_achieved",
            "transport": "builtin",
        },
        "need_more_info": {
            "description": (
                "Call this tool when you cannot proceed without additional information from the user."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "What specific information is needed from the user.",
                    },
                },
                "required": ["question"],
            },
            "server": "__builtin__",
            "original_name": "need_more_info",
            "transport": "builtin",
        },
    }

    async def _initialize_components(self):
        """Initialize LLM client and tool registry with discovered tools"""
        self.logger.info("Initializing agent components...")

        self.available_tools = await self.tool_registry.discover_tools()
        # Register built-in tools alongside MCP tools
        self.available_tools.update(self.BUILTIN_TOOLS)
        self.agent_tools = set(self.available_tools.keys())
        skills = self.load_all_skills()
        enabled_tools = self.get_enabled_agent_tools()
        
        self.logger.info(f"Discovered {len(self.available_tools)} tools: {list(self.available_tools.keys())}")
        self.logger.info(f"LLM Backend: {LLM_BACKEND}")
        
        if LLM_BACKEND.lower() == "ollama":
            print("Using Ollama (local) for orchestration")
            from ollama_client import OllamaClient
            self.llm_client = OllamaClient(enabled_tools)
        else:
            print("Using Gemini (API) for orchestration")
            from gemini_client import GeminiClient
            self.llm_client = GeminiClient(enabled_tools, skills)

    async def close(self):
        """Explicit async cleanup for tool registry resources."""
        await self.tool_registry.close()

    def get_enabled_agent_tools(self) -> Dict[str, Dict]:
        return {name: info for name, info in self.available_tools.items() if name in self.agent_tools}

    def _load_disabled_tools(self) -> Set[str]:
        # Tool state is now stored per-user in the database.
        return set()

    def _save_disabled_tools(self):
        # Tool state is now stored per-user in the database.
        pass

    def enable_tool(self, tool_name: str):
        if tool_name in self.available_tools and tool_name not in self.agent_tools:
            self.agent_tools.add(tool_name)
            self._refresh_agent_components()
            self._save_disabled_tools()
        elif tool_name in self.agent_tools:
            print(f"Tool already enabled: {tool_name}")
        else:
            print(f"Tool not found in available_tools: {tool_name}")

    def disable_tool(self, tool_name: str):
        if tool_name in self.agent_tools:
            self.agent_tools.remove(tool_name)
            self._refresh_agent_components()
            self._save_disabled_tools()
        else:
            print(f"Tool not enabled: {tool_name}")

    def _refresh_agent_components(self):
        enabled_tools = self.get_enabled_agent_tools()
        if self.llm_client:
            self.llm_client.update_tools(enabled_tools)

    def set_patient_focus(self, patient_id: str, patient_name: str):
        """Set the agent to focus on a specific patient for healthcare conversations"""
        patient_prompt = f"""You are a healthcare AI assistant. You help medical professionals by analyzing medical images, parsing DICOM files, generating radiology reports, and retrieving patient data.

You are currently focused on a specific patient:
- Name: {patient_name}
- Patient ID: {patient_id}

All tool calls and analysis should be in the context of this patient. If any tool returns data for a different patient, flag it immediately.

1. **DISCOVERY (Current State):** You can see the "Available Skills" list above. If a user asks "What can you do?", explain these skills based on their descriptions. Do NOT call a tool just to list them.
2. **READ SKILL:** When a task requires a specific skill, call `skills.read_skill_file(skill_name)` to get the detailed instructions and rules (SKILL.md) for that domain.
3. **EXPLORE REFERENCES:** If you need deeper technical details or schemas mentioned in the SKILL.md, then use `skills.read_references(skill_name, file_path)` to read specific reference files.
4. **EXECUTE:** After reading the skill instructions, proceed to use the specific domain tools (e.g., `monai.*`, `fhir.*`). If the skill has executable scripts, use `skills.execute_script(skill_name, script_name, parameters)`.

You have access to MCP tools that you can call directly. The tools are already registered and available to you - use them when the user requests an action.

BACKGROUND TASK RULES (read carefully):
- Any operation that takes more than a few seconds MUST be queued with `queue_task` instead of called directly.
- This includes: MONAI inference (monai.run_inference), report generation, bulk analysis of multiple files.
- After calling `queue_task`, respond to the user immediately - do NOT wait for the task to finish.
- The user will receive a notification in the UI when the task is done.
- For 'inference' tasks: input_data = {{"image_path": "...", "model_name": "..."}}
- For 'report' tasks: input_data = {{"task_ids": [...], "patient_context": {{...}}}}
- Short operations (analyze_image, list_models, download_model, FHIR queries) can still be called directly.

CONVERSATION RULES:
1. Be conversational. If the user greets you, greet them back. If they ask a question you can answer from context, answer it directly without calling any tool.
2. You have memory of previous interactions in this session. If the user asks about something that was already retrieved (e.g. patient name, modality, body part), answer from what you already know - do not re-call the tool.
3. Respond concisely and directly. Do not over-explain your reasoning.

TOOL USAGE RULES:
1. Only call a tool when the user requests an action that requires it AND the required parameters are available.
2. NEVER invent file paths. If a tool needs a file path, use the one from "FILES AVAILABLE" in the context. If none is available, ask the user to upload or provide one.
3. For DICOM files (.dcm): parse the metadata first to extract modality and body part before selecting models or running inference.
4. MONAI models require 3D volumes (.nii, .nii.gz). If the image is a single 2D slice, inform the user.
5. Do not repeat a tool call that already failed. Explain the error and ask how to proceed.
6. After a tool returns results, summarize them clearly for the user.
7. MULTI-FILE RULE: When multiple paths are listed in "FILES AVAILABLE" and the user asks to analyze or run inference, process ALL of them. Call the appropriate tool for each path one by one. Do not stop after the first.
8. DIRECTORY RULE: A path marked as [DICOM SERIES DIR] is a directory of DICOM slices that forms a single 3D volume. Pass the directory path directly to analyze_image or run_inference — MONAI handles it natively. Do NOT iterate or process individual files inside the directory."""
        
        if self.llm_client:
            self.llm_client.update_system_prompt(patient_prompt)
        self.session_context.set_patient(patient_id, patient_name)

    def reset_session_context(self):
        """Clear all accumulated session context."""
        self.session_context.clear()
        print("Session context cleared.")

    def save_context_to_db(self, session_id: str):
        """Persist current session context entries to the database."""
        import database as db
        # Clear existing DB entries for this session, then save current state
        db.clear_session_context(session_id)
        for entry in self.session_context.entries:
            db.save_context_entry(
                session_id,
                entry["tool"],
                entry["summary"],
                entry.get("data", {}),
                entry.get("timestamp", datetime.now().isoformat())
            )
        print(f"Saved {len(self.session_context.entries)} context entries to DB.")

    def load_context_from_db(self, session_id: str):
        """Restore session context from the database."""
        import database as db
        entries = db.load_session_context(session_id)
        self.session_context.clear()
        self.session_context.entries = entries
        print(f"Loaded {len(entries)} context entries from DB.")

    def _record_and_persist(self, tool_name: str, result_summary: str, key_data: Dict, session_id: str = None):
        """Record to in-memory context AND persist to DB."""
        self.session_context.record(tool_name, result_summary, key_data)
        if session_id:
            import database as db
            timestamp = self.session_context.entries[-1].get("timestamp", datetime.now().isoformat())
            db.save_context_entry(session_id, tool_name, result_summary, key_data, timestamp)

    def _extract_key_data(self, tool_name: str, result: Any) -> Dict[str, Any]:
        """Extract the key facts from a tool result for session context."""
        if not isinstance(result, dict):
            return {}

        # DICOM parsing - most critical for cross-query context
        if tool_name == "utils.parse_dicom":
            tags = result.get("tags", {})
            return {
                "modality": tags.get("Modality"),
                "body_part": tags.get("BodyPartExamined"),
                "patient_name": tags.get("PatientName"),
                "patient_id": tags.get("PatientID"),
                "study_description": tags.get("StudyDescription"),
                "dimensions": result.get("dimensions"),
                "is_valid": result.get("is_valid"),
            }

        if tool_name == "utils.parse_dicom_directory":
            return {
                "total_files": result.get("total_files"),
                "num_series": result.get("num_series"),
                "modalities_found": result.get("modalities", []),
            }

        # MONAI tools
        if tool_name == "monai.analyze_image":
            analysis = result.get("analysis", {})
            return {
                "detected_modalities": analysis.get("detected_modalities", []),
                "shape": result.get("shape"),
                "path": result.get("path") or result.get("file_path"),
            }

        if tool_name == "monai.list_models":
            models = result.get("models", [])
            return {
                "total_models": result.get("total", 0),
                "models": [
                    {"name": m.get("name"), "modality": m.get("modality"),
                     "body_part": m.get("body_part"), "downloaded": m.get("downloaded")}
                    for m in models
                ],
            }

        if tool_name == "monai.download_model":
            return {
                "model_name": result.get("model_name"),
                "status": result.get("status"),
            }

        if tool_name == "monai.run_inference":
            results_data = result.get("results", {})
            return {
                "status": result.get("status"),
                "model_used": result.get("model_name"),
                "detected_structures": results_data.get("detected_structures", []),
                "output_path": results_data.get("output_path"),
            }

        # FHIR tools
        if tool_name.startswith("fhir."):
            resource_type = result.get("resourceType")
            if resource_type == "Bundle":
                entries = result.get("entry", [])
                return {
                    "resource_type": "Bundle",
                    "entry_count": len(entries),
                    "entry_types": list(set(
                        e.get("resource", {}).get("resourceType", "?") for e in entries
                    )),
                }
            elif resource_type:
                return {"resource_type": resource_type, "id": result.get("id")}

        # RadLex tools
        if tool_name.startswith("radlex."):
            return {
                "operation": tool_name.split(".")[-1],
                "status": result.get("status", "completed"),
            }

        return {}
    async def refresh_server_tools(self, name: str):
        new_tools = await self.tool_registry.refresh_server_tools(name)
        old = [k for k in self.available_tools if k.startswith(f"{name}.")]
        for k in old:
            self.available_tools.pop(k, None)
            self.agent_tools.discard(k)
        self.available_tools.update(new_tools)
        self.agent_tools.update(new_tools.keys())
        self._refresh_agent_components()
        return new_tools

    async def add_mcp_server(self, name: str, cfg: dict):
        new_tools = await self.tool_registry.add_server(name, cfg)
        self.available_tools.update(new_tools)
        self.agent_tools.update(new_tools.keys())
        self._refresh_agent_components()
        return new_tools

    async def remove_mcp_server(self, name: str):
        await self.tool_registry.remove_server(name)
        to_remove = [k for k in self.available_tools if k.startswith(f"{name}.")]
        for k in to_remove:
            self.available_tools.pop(k, None)
            self.agent_tools.discard(k)
        self._refresh_agent_components()

    async def refresh_available_tools(self):
        previous_tools = set(self.available_tools.keys())
        previous_enabled = set(self.agent_tools)
        self.available_tools = await self.tool_registry.reload_config_and_refresh()
        current_tools = set(self.available_tools.keys())
        still_enabled = previous_enabled & current_tools
        new_tools = current_tools - previous_tools
        self.agent_tools = still_enabled | new_tools
        self.agent_tools &= current_tools
        self._refresh_agent_components()

    
    def load_all_skills(self):
        """
        Scans the skills directory, finds SKILL.md files, and loads their metadata.
        Returns formatted text listing available skills for the system prompt.
        """
        skills_text = []
        
        if not SKILL_DIR_PATH.exists():
            return "No skills directory found."

        # Iterate through every sub-folder in the root skills directory
        for skill_folder in SKILL_DIR_PATH.iterdir():
            if not skill_folder.is_dir():
                continue
                
            skill_file = skill_folder / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text()
                    # Split YAML frontmatter from Markdown body
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        metadata = yaml.safe_load(frontmatter)
                        
                        skill_name = metadata.get("name", skill_folder.name)
                        skill_description = metadata.get("description", "No description")
                        skills_text.append(f"- **{skill_name}**: {skill_description}")
                except Exception as e:
                    print(f"Error loading skill {skill_folder.name}: {e}")
        
        return "\n".join(skills_text) if skills_text else "No skills available"
    

    async def confirm_tool_execution(self, session_id: str = None) -> Optional[Dict]:
        """Execute the pending tool after user confirmation"""
        if not self.pending_tool_call:
            return {"error": "No pending tool call to confirm"}

        pending = self.pending_tool_call
        self.pending_tool_call = None

        # Execute the tool
        tool_name = pending["tool_name"]
        arguments = pending["arguments"]
        print(f"Confirmed - Executing: {tool_name}")
        
        self.logger.info("\nTOOL CONFIRMATION APPROVED:")
        self.logger.info(f"  Tool: {tool_name}")
        self.logger.info("  User confirmed execution")
        self.logger.info("\nTOOL CALL REQUESTED:")
        self.logger.info(f"  Tool: {tool_name}")
        self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")

        result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)
        
        self.logger.info("\nTOOL RESULT:")
        self.logger.info(f"  Tool: {tool_name}")
        result_full = json.dumps(result, indent=4) if isinstance(result, dict) else str(result)
        self.logger.info(f"  Result: {result_full}")

        # Check if result contains an error
        is_error = False
        if isinstance(result, dict):
            is_error = result.get("is_error") or result.get("error")

        execution_history = pending["execution_history"]

        is_gemini = LLM_BACKEND.lower() != "ollama"

        if result and not is_error:
            result_summary = self._create_result_summary(tool_name, result)
            execution_history.append({
                "tool": tool_name,
                "success": True,
                "result_summary": result_summary,
                "result": result
            })
            # Record to session context for cross-query memory
            key_data = self._extract_key_data(tool_name, result)
            self._record_and_persist(tool_name, result_summary, key_data, session_id)
            print(f"Tool succeeded: {result_summary}")

            self.logger.info("  Status: SUCCESS")
            self.logger.info(f"  Summary: {result_summary}")

            # Save radlex reports to DB so they appear in the Report tab
            if session_id and tool_name == "radlex.generate_report":
                from datetime import datetime as _dt
                _report_wrap = {
                    "patient_context": {},
                    "findings": [],
                    "radlex_template": result,
                    "narrative": {},
                    "generated_at": _dt.now().isoformat(),
                }
                _rtid = db.create_task(session_id, "report", "Radlex Template Report", arguments)
                db.update_task(_rtid, "done", result=_report_wrap)
                print(f"[agent] Saved radlex report to DB as task {_rtid[:8]}")

            confirmed_result = result
        else:
            error_msg = result.get("error") if result else "No result"
            execution_history.append({
                "tool": tool_name,
                "success": False,
                "error": error_msg
            })
            print(f"Tool failed: {error_msg}")

            self.logger.error("  Status: FAILED")
            self.logger.error(f"  Error: {error_msg}")

            confirmed_result = {"error": str(error_msg) if error_msg else "Tool execution failed", "is_error": True}

        # Build the accumulated results list for this turn:
        # results confirmed so far (from before this call) + this call's result
        turn_accumulated_results = list(pending.get("turn_accumulated_results", [])) + [(tool_name, confirmed_result)]
        turn_remaining_calls = list(pending.get("turn_remaining_calls", []))
        _pending_user_id = pending.get("user_id")
        _pending_session_id = pending.get("session_id")

        # Process any built-in tools at the front of the remaining calls immediately
        while turn_remaining_calls:
            next_name, next_args = turn_remaining_calls[0]
            if next_name == "list_tasks":
                turn_remaining_calls.pop(0)
                tasks = db.list_tasks(user_id=_pending_user_id) if _pending_user_id else db.list_tasks(session_id=_pending_session_id)
                _summary = [
                    {
                        "id": t["id"],
                        "type": t["task_type"],
                        "description": t["description"],
                        "status": t["status"],
                        "error": t.get("error"),
                    }
                    for t in tasks
                ]
                _result = {
                    "tasks": _summary,
                    "running": sum(1 for t in tasks if t["status"] in ("queued", "running")),
                    "done": sum(1 for t in tasks if t["status"] == "done"),
                    "failed": sum(1 for t in tasks if t["status"] == "failed"),
                }
                _result_summary = f"Tasks: {_result['running']} running, {_result['done']} done, {_result['failed']} failed"
                execution_history.append({
                    "tool": next_name,
                    "success": True,
                    "result_summary": _result_summary,
                    "result": _result,
                })
                turn_accumulated_results.append((next_name, _result))
            elif next_name == "queue_task":
                turn_remaining_calls.pop(0)
                _task_type = next_args.get("task_type", "generic")
                _description = next_args.get("description", "Background task")
                _input_data = next_args.get("input_data", {})
                _task_id = task_runner.submit_task(
                    session_id=session_id or "unknown",
                    task_type=_task_type,
                    description=_description,
                    input_data=_input_data,
                )
                _result = {
                    "task_id": _task_id,
                    "status": "queued",
                    "message": f"Task queued: '{_description}'. You'll receive a notification when it finishes.",
                }
                execution_history.append({
                    "tool": next_name,
                    "success": True,
                    "result_summary": f"Queued background task: {_description}",
                    "result": _result,
                })
                turn_accumulated_results.append((next_name, _result))
            elif next_name == "monai.run_inference":
                turn_remaining_calls.pop(0)
                _image_path = next_args.get("image_path", "")
                _model_name = next_args.get("model_name", "")
                _body_part = next(
                    (e["data"].get("body_part", "") for e in reversed(self.session_context.entries)
                     if e.get("data", {}).get("body_part")), ""
                )
                _modality = next(
                    (e["data"].get("modality", "") for e in reversed(self.session_context.entries)
                     if e.get("data", {}).get("modality")), ""
                )
                _queued_tasks = []
                if _image_path:
                    _inf_fname = Path(_image_path).name
                    _inf_desc = f"Inference: {_inf_fname}" + (f" ({_model_name})" if _model_name else "")
                    _inf_task_id = task_runner.submit_task(
                        session_id=session_id or "unknown",
                        task_type="inference",
                        description=_inf_desc,
                        input_data={
                            "image_path": _image_path,
                            "model_name": _model_name,
                            "body_part": _body_part,
                            "modality": _modality,
                        },
                    )
                    _queued_tasks.append({"task_id": _inf_task_id, "file": _inf_fname})
                _result = {
                    "tasks_queued": len(_queued_tasks),
                    "tasks": _queued_tasks,
                    "message": f"Queued inference for {len(_queued_tasks)} file(s) using {_model_name}. Results will appear in the Results tab.",
                }
                execution_history.append({
                    "tool": next_name,
                    "success": True,
                    "result_summary": f"Queued {len(_queued_tasks)} inference task(s)",
                    "result": _result,
                })
                turn_accumulated_results.append((next_name, _result))
            else:
                # Not a built-in tool — stop draining; this needs confirmation
                break

        # If there are still remaining MCP calls that need confirmation, chain to next one
        if turn_remaining_calls:
            next_name, next_args = turn_remaining_calls.pop(0)
            self.logger.info("\nCHAINED CONFIRMATION REQUIRED:")
            self.logger.info(f"  Tool: {next_name}")
            self.logger.info(f"  Arguments: {json.dumps(next_args, indent=4)}")
            self.pending_tool_call = {
                "tool_name": next_name,
                "arguments": next_args,
                "goal": pending["goal"],
                "execution_history": execution_history,
                "fileList": pending["fileList"],
                "data": pending["data"],
                "metadata": pending["metadata"],
                "iterations_used": pending["iterations_used"],
                "max_iterations": pending["max_iterations"],
                "session_id": pending.get("session_id"),
                "user_id": pending.get("user_id"),
                "turn_accumulated_results": turn_accumulated_results,
                "turn_remaining_calls": turn_remaining_calls,
            }
            return {
                "type": "confirmation_required",
                "tool_name": next_name,
                "arguments": next_args,
                "message": f"About to execute: {next_name}",
                "execution_history": execution_history
            }

        # All calls in the turn are resolved — send accumulated results to Gemini
        llm_response = None
        if is_gemini and turn_accumulated_results:
            self.logger.info(f"\nSENDING {len(turn_accumulated_results)} RESULT(S) TO LLM after confirmation")
            try:
                if len(turn_accumulated_results) > 1:
                    llm_response = self.llm_client.send_multiple_function_responses(turn_accumulated_results)
                else:
                    _single_name, _single_data = turn_accumulated_results[0]
                    llm_response = self.llm_client.send_function_response(_single_name, _single_data)
                self.logger.info("Captured LLM response from function_response(s) (Gemini)")
            except Exception as llm_err:
                print(f"LLM API error after tool execution: {type(llm_err).__name__}: {llm_err}")
                return {"error": f"Tool executed but LLM API unreachable: {llm_err}", "is_error": True}

        # Continue the task from where we left off
        # Only pass _resume_response if using Gemini
        return await self.execute_task(
            goal=pending["goal"],
            data=pending["data"],
            fileList=pending["fileList"],
            max_iterations=pending["max_iterations"] - pending["iterations_used"],
            metadata=pending["metadata"],
            session_id=pending.get("session_id"),
            user_id=pending.get("user_id"),
            _resume_history=execution_history,
            _resume_response=llm_response if is_gemini else None
        )

    def deny_tool_execution(self) -> Dict:
        """Cancel the pending tool call"""
        if not self.pending_tool_call:
            return {"error": "No pending tool call to deny"}

        tool_name = self.pending_tool_call["tool_name"]
        self.pending_tool_call = None
        print(f"Denied - Tool not executed: {tool_name}")

        return {
            "type": "agent_response",
            "answer": f"Tool '{tool_name}' was not executed. How would you like to proceed?",
            "tools_used": [],
            "success": False
        }

    def get_pending_tool(self) -> Optional[Dict]:
        """Get the pending tool call details"""
        return self.pending_tool_call

    def set_mode(self, mode: str):
        """Switch between 'debug' (confirmation required, raw output) and 'normal' (auto-execute, professional responses)."""
        self.mode = mode
        if mode == 'normal':
            self.require_confirmation = False
            if self.llm_client and hasattr(self.llm_client, 'set_mode_extension'):
                self.llm_client.set_mode_extension(NORMAL_MODE_COMMUNICATION_RULES)
        else:  # debug
            self.require_confirmation = True
            if self.llm_client and hasattr(self.llm_client, 'set_mode_extension'):
                self.llm_client.set_mode_extension("")
        print(f"[agent] Mode set to '{mode}' (require_confirmation={self.require_confirmation})")

    def set_agent_type(self, autonomous: bool):
        """Set whether the agent is currently executing autonomously or not (for logging and response formatting)"""
        self.is_agent_autonomous = autonomous
        print(f"[agent] Autonomous execution set to {autonomous}")

    async def execute_task(self, goal: str, data: Any = None, fileList: Any = None, max_iterations: int = 20, metadata: Dict = None, _resume_history: List = None, _resume_response: Optional[Any] = None, session_id: str = None, user_id: str = None) -> Optional[Dict]:
        """
        Truly autonomous task execution - agent reasons about tools and executes

        Args:
            goal: Natural language description of what to accomplish
            data: Optional data context (e.g., patient data to save)
            fileList: Optional list of images for processing
            max_iterations: Maximum number of tool executions allowed
            metadata: Optional dict with modality, body_part for filtering models
            _resume_history: Optional execution history to resume from
            _resume_response: Optional LLM response to use instead of generating new one

        Returns:
            Final result if successful, None if goal not achieved
        """
        print(f"\n{'='*80}")    
        print("Autonomous agent: ", self.is_agent_autonomous)
        print(f"Starting autonomous task: {goal}")
        self.logger.info("=" * 80)
        self.logger.info(f"TASK START: {goal}")
        self.logger.info(f"Max iterations: {max_iterations}")
        if metadata:
            self.logger.info(f"Metadata: {json.dumps(metadata, indent=2)}")
        if fileList:
            self.logger.info(f"Files provided: {len(fileList)} file(s)")
        if data:
            self.logger.info(f"Data provided: {len(str(data))} chars")
        
        if metadata:
            print(f"Metadata: modality={metadata.get('modality')}, body_part={metadata.get('body_part')}")

        execution_history = _resume_history if _resume_history else []
        iterations = 0
        final_result = None
        _inference_queued: set = set()  # Track image paths already queued for inference

        # Extract image path for workflow
        image_path = None
        if fileList and isinstance(fileList, list) and fileList:
            image_path = fileList[0][0]  # First image's temp file path
            print(f"Image path for workflow: {image_path}")

        # Both Ollama and Gemini now use true agentic approach
        # The LLM decides which tools to call based on context

        while iterations < max_iterations:
            iterations += 1
            print(f"Iteration {iterations}/{max_iterations}")
            try:
                # Note: Execution history is now managed by Gemini's chat session
                # We don't need to build history_text anymore - it's redundant!
                
                # Prompt agent to decide next action OR declare success
                data_context = ""
                if data:
                    data_context = f"\n\nDATA AVAILABLE:\n{json.dumps(data, indent=2)}" if len(json.dumps(data)) > 500 else f"\n\nDATA AVAILABLE:\n{json.dumps(data, indent=2)}"
                
                image_context = "\n\nFILES AVAILABLE: None. User has not uploaded any images."
                images_for_llm = None  # Only pass 2D images to LLM (if supported)

                if fileList:
                    # Handle fileList as (filepath, content) tuples
                    if isinstance(fileList, list) and fileList:
                        # Separate files and directories so the LLM knows which is which
                        file_paths = []
                        dir_paths = []
                        for temp_filepath, _ in fileList:
                            if os.path.isdir(temp_filepath):
                                dir_paths.append(temp_filepath)
                            else:
                                file_paths.append(temp_filepath)

                        parts = []
                        if file_paths:
                            parts.append("Files: " + ", ".join(file_paths))
                        if dir_paths:
                            parts.append("DICOM series directories (treat each as a single 3D volume — use the directory path directly): " + ", ".join(f"[DICOM SERIES DIR] {p}" for p in dir_paths))
                        image_context = "\n\nFILES AVAILABLE: Yes\n" + "\n".join(parts)

                        # Only pass small 2D images to LLM, skip large 3D medical files and directories
                        images_for_llm = []
                        for temp_filepath, content in fileList:
                            # Skip directories — cannot be sent to LLM as images
                            if os.path.isdir(temp_filepath):
                                continue
                            ext = temp_filepath.lower()
                            # Skip 3D formats - too large, LLM can't visualize
                            if not ext.endswith(('.nii', '.nii.gz', '.dcm', '.mha', '.mhd', '.nrrd')):
                                # Only include if file is small enough (< 5MB)
                                if len(content) < 5 * 1024 * 1024:
                                    images_for_llm.append((temp_filepath, content))

                        if not images_for_llm:
                            images_for_llm = None
                    else:
                        image_context = "\n\nFILES AVAILABLE:\nImage data provided"

                # Build session context from previous queries
                session_ctx = self.session_context.build_context_string()
                session_block = f"\n\n{session_ctx}" if session_ctx else ""

                # Check if we're using Gemini and have a response from previous send_function_response
                is_gemini = LLM_BACKEND.lower() != "ollama"
                
                if is_gemini and _resume_response is not None:
                    # Gemini optimization: Use the response we already got from send_function_response
                    response = _resume_response
                    _resume_response = None  # Clear for next iteration
                    
                    self.logger.info(f"\n{'='*60}")
                    self.logger.info(f"ITERATION {iterations}/{max_iterations}")
                    self.logger.info(f"{'='*60}")
                    self.logger.info("\nUSING RESPONSE FROM send_function_response (no redundant prompt)\n")
                    self.logger.info(f"\nLLM RAW RESPONSE:\n{response}\n")
                    
                    print("Using response from send_function_response (Gemini optimization)")
                else:
                    # Standard flow: prompt the LLM (always for Ollama, or first iteration for Gemini)
                    if not execution_history:
                        # First iteration - include session context so agent knows what happened before
                        prompt = f"""GOAL: {goal}{data_context}{image_context}{session_block}

Analyze the goal and decide your next action."""
                    else:
                        # After tool execution - ask for evaluation
                        # For Ollama: Build execution history into the prompt since we don't use send_function_response
                        history_text = ""
                        if not is_gemini and execution_history:
                            history_text = "\n\nExecution history:\n"
                            for i, event in enumerate(execution_history, 1):
                                history_text += f"{i}. Called {event['tool']} → "
                                if event['success']:
                                    # Show the actual result so agent can evaluate
                                    result_summary = event.get('result_summary', 'Success')
                                    result_data = event.get('result', {})
                                    history_text += f"Success. Result: {result_summary}\n"
                                    if result_data:
                                        # Add truncated response for context
                                        result_str = json.dumps(result_data, indent=2)
                                        if len(result_str) > 500:
                                            history_text += f"   Response data (truncated): {result_str[:500]}...\n"
                                        else:
                                            history_text += f"   Response data: {result_str}\n"
                                else:
                                    error_msg = event.get('error') or 'Unknown error'
                                    # Ensure error is never None
                                    if error_msg is None or (isinstance(error_msg, str) and not error_msg.strip()):
                                        error_msg = 'Tool execution failed'
                                    history_text += f"Failed: {error_msg}\n"
                        
                        prompt = f"""{history_text}
Does this accomplish the goal?
- If YES: Call the goal_achieved tool with a summary of what was accomplished
- If NO: Call the next tool you need
- If you need more information from the user: Call the need_more_info tool

Your decision:"""

                    print(f"Prompt: {prompt}")

                    self.logger.info(f"\n{'='*60}")
                    self.logger.info(f"ITERATION {iterations}/{max_iterations}")
                    self.logger.info(f"{'='*60}")
                    self.logger.info(f"\nPROMPT SENT TO LLM:\n{prompt}\n")
                    if images_for_llm:
                        self.logger.info(f"Images attached: {len(images_for_llm)} file(s)")
                    
                    # Prepare content with actual images for Gemini
                    content_parts = [prompt]
                    
                    response = self.llm_client.generate_content(content_parts, images_for_llm)
                    self.logger.info(f"\nLLM RAW RESPONSE:\n{response}\n")
                
                # Check if agent declares success (text response, no tool call)
                has_text = False
                has_function_call = False

                # --- Phase 1: scan all parts for text signals and collect function calls ---
                _turn_calls: list = []  # list of (tool_name, arguments) for this turn

                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            has_text = True
                            text_content = part.text.strip().upper()
                            if "GOAL_ACHIEVED" in text_content or "GOAL ACHIEVED" in text_content:
                                self.logger.warning("LLM used text GOAL_ACHIEVED instead of goal_achieved tool — falling back to string detection")
                                print("Agent declares: Goal achieved! (text fallback)")
                                # Fallback: return detailed response with execution history
                                answer = self._extract_answer_from_results(part.text, execution_history, final_result)
                                tools_used = [event['tool'] for event in execution_history if event['success']]

                                self.logger.info(f"\n{'='*60}")
                                self.logger.info("TASK COMPLETED SUCCESSFULLY")
                                self.logger.info(f"  Iterations used: {iterations}")
                                self.logger.info(f"  Tools used: {tools_used}")
                                self.logger.info(f"  Answer: {answer}")
                                self.logger.info(f"{'='*80}\n")

                                return {
                                    "type": "agent_response",
                                    "answer": answer,
                                    "tools_used": tools_used,
                                    "execution_history": execution_history,
                                    "success": True
                                }

                            if "NEED MORE INFO" in text_content:
                                self.logger.warning("LLM used text NEED MORE INFO instead of need_more_info tool — falling back to string detection")
                                print("Agent requests more information to proceed. (text fallback)")
                                return {
                                    "type": "agent_response",
                                    "answer": part.text.strip(),
                                    "tools_used": [],
                                    "execution_history": execution_history,
                                    "success": False
                                }

                        if hasattr(part, 'function_call') and part.function_call:
                            has_function_call = True
                            _raw_name = part.function_call.name
                            _raw_args = dict(part.function_call.args)
                            # Resolve tool name if missing prefix
                            if _raw_name not in self.available_tools:
                                for full_name in self.available_tools.keys():
                                    if full_name.endswith(f".{_raw_name}"):
                                        print(f"Resolved tool name: {_raw_name} -> {full_name}")
                                        _raw_name = full_name
                                        break
                            _turn_calls.append((_raw_name, _raw_args))

                # --- Phase 2: process each function call in the turn ---
                _turn_results: list = []  # list of (tool_name, result_data) to send to Gemini together

                for tool_name, arguments in _turn_calls:

                    # Check if agent is repeating a failed tool (block only after 2 consecutive failures)
                    if len(execution_history) >= 2:
                        last_event = execution_history[-1]
                        prev_event = execution_history[-2]
                        if (
                            last_event.get('tool') == tool_name and not last_event.get('success')
                            and prev_event.get('tool') == tool_name and not prev_event.get('success')
                        ):
                            print(f"Agent tried to repeat tool '{tool_name}' after 2 consecutive failures - skipping and prompting for alternative")
                            execution_history.append({
                                "tool": tool_name,
                                "success": False,
                                "error": f"Repetition prevented: Tool '{tool_name}' failed twice consecutively. Try a different tool."
                            })
                            _turn_results.append((tool_name, {"error": f"Repetition prevented: Tool '{tool_name}' failed twice consecutively. Try a different tool.", "is_error": True}))
                            continue

                    # --- Built-in tool intercept ---
                    # Handle built-in tools locally without going to MCP
                    if tool_name == "list_tasks":
                        tasks = db.list_tasks(user_id=user_id) if user_id else db.list_tasks(session_id=session_id)
                        summary = [
                            {
                                "id": t["id"],
                                "type": t["task_type"],
                                "description": t["description"],
                                "status": t["status"],
                                "error": t.get("error"),
                            }
                            for t in tasks
                        ]
                        result = {
                            "tasks": summary,
                            "running": sum(1 for t in tasks if t["status"] in ("queued", "running")),
                            "done": sum(1 for t in tasks if t["status"] == "done"),
                            "failed": sum(1 for t in tasks if t["status"] == "failed"),
                        }
                        result_summary = f"Tasks: {result['running']} running, {result['done']} done, {result['failed']} failed"
                        execution_history.append({
                            "tool": tool_name,
                            "success": True,
                            "result_summary": result_summary,
                            "result": result,
                        })
                        final_result = result
                        _turn_results.append((tool_name, result))
                        continue

                    if tool_name == "queue_task":
                        task_type = arguments.get("task_type", "generic")
                        description = arguments.get("description", "Background task")
                        input_data = arguments.get("input_data", {})
                        task_id = task_runner.submit_task(
                            session_id=session_id or "unknown",
                            task_type=task_type,
                            description=description,
                            input_data=input_data,
                        )
                        result = {
                            "task_id": task_id,
                            "status": "queued",
                            "message": f"Task queued: '{description}'. You'll receive a notification when it finishes.",
                        }
                        result_summary = f"Queued background task: {description}"
                        execution_history.append({
                            "tool": tool_name,
                            "success": True,
                            "result_summary": result_summary,
                            "result": result,
                        })
                        final_result = result
                        _turn_results.append((tool_name, result))
                        continue

                    if tool_name == "goal_achieved":
                        summary = arguments.get("summary", "")
                        answer = summary if summary else self._extract_answer_from_results("", execution_history, final_result)
                        tools_used = [event['tool'] for event in execution_history if event.get('success')]

                        self.logger.info(f"\n{'='*60}")
                        self.logger.info("TASK COMPLETED VIA goal_achieved TOOL")
                        self.logger.info(f"  Iterations used: {iterations}")
                        self.logger.info(f"  Tools used: {tools_used}")
                        self.logger.info(f"  Answer: {answer}")
                        self.logger.info(f"{'='*60}\n")

                        return {
                            "type": "agent_response",
                            "answer": answer,
                            "tools_used": tools_used,
                            "execution_history": execution_history,
                            "success": True
                        }

                    if tool_name == "need_more_info":
                        question = arguments.get("question", "I need more information to proceed.")
                        return {
                            "type": "agent_response",
                            "answer": question,
                            "tools_used": [],
                            "execution_history": execution_history,
                            "success": False
                        }

                    # run_inference always runs in the background so the user
                    # can keep chatting and the result lands in the Results tab.
                    if tool_name == "monai.run_inference" and not self.is_agent_autonomous:
                        image_path = arguments.get("image_path", "")
                        model_name = arguments.get("model_name", "")
                        # Pull body_part/modality from session context (set by analyze_image)
                        body_part = next(
                            (e["data"].get("body_part", "") for e in reversed(self.session_context.entries)
                             if e.get("data", {}).get("body_part")), ""
                        )
                        modality = next(
                            (e["data"].get("modality", "") for e in reversed(self.session_context.entries)
                             if e.get("data", {}).get("modality")), ""
                        )

                        # Only queue the exact path the LLM specified with the model it chose.
                        # Do NOT auto-queue other files here — the LLM will call run_inference
                        # separately for each file with the appropriate model (per system prompt rule 7).
                        # Auto-queuing all files with the same model caused wrong-model assignments
                        # when the LLM intended different models for different files.
                        all_unqueued = [image_path]

                        queued_tasks = []
                        for inf_path in all_unqueued:
                            if inf_path in _inference_queued:
                                continue
                            inf_fname = Path(inf_path).name if inf_path else "unknown"
                            inf_desc = f"Inference: {inf_fname}" + (f" ({model_name})" if model_name else "")
                            inf_task_id = task_runner.submit_task(
                                session_id=session_id or "unknown",
                                task_type="inference",
                                description=inf_desc,
                                input_data={
                                    "image_path": inf_path,
                                    "model_name": model_name,
                                    "body_part": body_part,
                                    "modality": modality,
                                },
                            )
                            _inference_queued.add(inf_path)
                            queued_tasks.append({"task_id": inf_task_id, "file": inf_fname})

                        result = {
                            "tasks_queued": len(queued_tasks),
                            "tasks": queued_tasks,
                            "message": f"Queued inference for {len(queued_tasks)} file(s) using {model_name}. Results will appear in the Results tab.",
                        }
                        result_summary = f"Queued {len(queued_tasks)} inference task(s)"
                        execution_history.append({
                            "tool": tool_name,
                            "success": True,
                            "result_summary": result_summary,
                            "result": result,
                        })
                        final_result = result
                        _turn_results.append((tool_name, result))
                        continue

                    # Check if confirmation is required
                    if self.require_confirmation:
                        print(f"Tool confirmation required: {tool_name}")

                        self.logger.info("\nTOOL CONFIRMATION REQUIRED:")
                        self.logger.info(f"  Tool: {tool_name}")
                        self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")

                        # Determine which calls in this turn come after this one.
                        # _turn_results has one entry per call processed before this one,
                        # so its length is the 0-based index of the current call.
                        _current_idx = len(_turn_results)
                        _remaining_calls = _turn_calls[_current_idx + 1:]

                        self.pending_tool_call = {
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "goal": goal,
                            "execution_history": execution_history,
                            "fileList": fileList,
                            "data": data,
                            "metadata": metadata,
                            "iterations_used": iterations,
                            "max_iterations": max_iterations,
                            "session_id": session_id,
                            "user_id": user_id,
                            "turn_accumulated_results": list(_turn_results),
                            "turn_remaining_calls": _remaining_calls,
                        }
                        return {
                            "type": "confirmation_required",
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "message": f"About to execute: {tool_name}",
                            "execution_history": execution_history
                        }

                    # Execute the tool
                    print(f"Executing: {tool_name}")

                    self.logger.info("\nTOOL CALL REQUESTED:")
                    self.logger.info(f"  Tool: {tool_name}")
                    self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")

                    result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)

                    self.logger.info("\nTOOL RESULT:")
                    self.logger.info(f"  Tool: {tool_name}")
                    result_full = json.dumps(result, indent=4) if isinstance(result, dict) else str(result)
                    self.logger.info(f"  Result: {result_full}")

                    # Check if result contains an error
                    is_error = False
                    if isinstance(result, dict):
                        is_error = result.get("is_error") or result.get("error") or "error" in str(result.get("text", "")).lower()

                    print(f"TOOL EXECUTION RESULT: {result}")
                    if result and not is_error:
                        # Create human-readable summary based on tool type
                        result_summary = self._create_result_summary(tool_name, result)

                        execution_history.append({
                            "tool": tool_name,
                            "success": True,
                            "result_summary": result_summary,
                            "result": result  # Store actual result
                        })

                        # Record to session context for cross-query memory
                        key_data = self._extract_key_data(tool_name, result)
                        self._record_and_persist(tool_name, result_summary, key_data, session_id)

                        final_result = result
                        print(f"Tool succeeded: {result_summary}")

                        self.logger.info("  Status: SUCCESS")
                        self.logger.info(f"  Summary: {result_summary}")

                        # Save radlex reports to DB so they appear in the Report tab
                        if session_id and tool_name == "radlex.generate_report":
                            from datetime import datetime as _dt
                            _report_wrap = {
                                "patient_context": {},
                                "findings": [],
                                "radlex_template": result,
                                "narrative": {},
                                "generated_at": _dt.now().isoformat(),
                            }
                            _rtid = db.create_task(session_id, "report", "Radlex Template Report", arguments)
                            db.update_task(_rtid, "done", result=_report_wrap)
                            print(f"[agent] Saved radlex report to DB as task {_rtid[:8]}")

                        _turn_results.append((tool_name, result))

                    elif result and is_error:
                        # Ensure error_msg is always a string, never None
                        error_msg = result.get("error") or result.get("text") or "Unknown error"
                        if error_msg is None or (isinstance(error_msg, str) and not error_msg.strip()):
                            error_msg = "Tool execution failed without error details"
                        execution_history.append({
                            "tool": tool_name,
                            "success": False,
                            "error": str(error_msg),  # Ensure it's a string
                            "result": result
                        })

                        # Persist a failed task record so the Results tab shows it
                        _RESULT_TOOLS = {"monai.analyze_image", "monai.run_inference", "monai.download_model"}
                        if session_id and tool_name in _RESULT_TOOLS:
                            _path = (arguments.get("path") or arguments.get("image_path") or "")
                            _label = {"monai.analyze_image": "Image Analysis",
                                      "monai.run_inference": "Inference",
                                      "monai.download_model": "Model Download"}.get(tool_name, tool_name)
                            _fname = Path(_path).name if _path else "unknown file"
                            _tid = db.create_task(session_id, "inference",
                                                  f"{_label}: {_fname}", {"path": _path, **arguments})
                            db.update_task(_tid, "failed", None, str(error_msg))

                        print(f"Tool failed: {error_msg}")

                        self.logger.error("  Status: FAILED")
                        self.logger.error(f"  Error: {error_msg}")

                        error_response = {"error": str(error_msg), "is_error": True}
                        _turn_results.append((tool_name, error_response))

                    else:
                        execution_history.append({
                            "tool": tool_name,
                            "success": False,
                            "error": "Execution returned no result"
                        })
                        print("Tool execution failed")

                        self.logger.error("  Status: FAILED - No result returned")

                        error_response = {"error": "Execution returned no result", "is_error": True}
                        _turn_results.append((tool_name, error_response))

                # --- Phase 3: send ALL accumulated results to Gemini in one message ---
                # For Ollama: skip this entirely — execution history goes into the next prompt
                if is_gemini and _turn_results:
                    if len(_turn_results) > 1:
                        self.logger.info(f"\nSENDING {len(_turn_results)} RESULTS TO LLM via send_multiple_function_responses")
                        _resume_response = self.llm_client.send_multiple_function_responses(_turn_results)
                    else:
                        _single_name, _single_data = _turn_results[0]
                        self.logger.info("\nSENDING FULL RESULT TO LLM via send_function_response")
                        _resume_response = self.llm_client.send_function_response(_single_name, _single_data)
                    self.logger.info("Captured response from function_response(s) - will use on next iteration")
                
                # If agent responded with text but no tool call
                if has_text and not has_function_call:
                    text_response = response.text.strip()
                    # Check if it's a GOAL_ACHIEVED response
                    if "GOAL_ACHIEVED" in text_response.upper() or "GOAL ACHIEVED" in text_response.upper():
                        pass  # Already handled above
                    elif len(text_response) > 20:
                        # Agent gave a substantial text response - return it
                        # This covers: conversational replies, error explanations, asking user for info
                        last_failed = execution_history and not execution_history[-1].get('success')
                        if last_failed:
                            print("Agent explaining tool error to user")
                        else:
                            print("Agent responded with text (no tools needed for this query)")
                        tools_used = [event['tool'] for event in execution_history if event.get('success')]
                        return {
                            "type": "agent_response",
                            "answer": text_response,
                            "tools_used": tools_used,
                            "execution_history": execution_history,
                            "success": not last_failed
                        }
                    else:
                        print("Agent response too short, continuing...")
                        execution_history.append({
                            "tool": "none",
                            "success": False,
                            "error": "Agent response was not actionable"
                        })
                    
            except Exception as e:
                print(f"Error in agentic workflow: {type(e).__name__}: {e}")
                self.logger.error(f"Exception in workflow: {type(e).__name__}: {e}")
                error_message = str(e) if e else "Unknown workflow error"

                # Stop immediately on rate limit errors - no point retrying
                if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    print(f"Rate limit hit - stopping: {error_message}")
                    return {
                        "type": "agent_response",
                        "answer": "API rate limit reached. Please wait a few minutes before trying again, or check your API quota.",
                        "tools_used": [],
                        "execution_history": execution_history,
                        "success": False
                    }

                execution_history.append({
                    "tool": "workflow",
                    "success": False,
                    "error": error_message,
                    "result": None
                })
        
        print("Max iterations reached or goal not achieved.")
        self.logger.warning(f"TASK ENDED: Max iterations reached ({max_iterations}) - goal not achieved")
        self.logger.info(f"Total successful tools: {sum(1 for e in execution_history if e.get('success'))}")
        self.logger.info(f"={'='*80}\n")
        return None
    
    def _create_result_summary(self, tool_name: str, result: Any) -> str:
        """Create a human-readable summary of tool results"""
        if not isinstance(result, dict):
            return "completed"

        # MONAI tools
        if tool_name == "monai.analyze_image":
            modality = result.get("analysis", {}).get("detected_modalities", ["unknown"])[0]
            shape = result.get("shape", [])
            return f"Image analyzed: {modality}, shape {shape}"

        elif tool_name == "monai.list_models":
            total = result.get("total", 0)
            models = result.get("models", [])
            downloaded = sum(1 for m in models if m.get("downloaded"))
            return f"Found {total} models ({downloaded} downloaded)"

        elif tool_name == "monai.download_model":
            status = result.get("status", "unknown")
            model_name = result.get("model_name", "unknown")
            return f"Model {model_name}: {status}"

        elif tool_name == "monai.run_inference":
            status = result.get("status", "unknown")
            results = result.get("results", {})
            detected = results.get("detected_structures", [])
            if detected:
                names = [s.get("name", "?") for s in detected]
                return f"Inference {status}: detected {', '.join(names)}"
            return f"Inference {status}"

        # RadLex tools
        elif tool_name.startswith("radlex."):
            if "template" in tool_name.lower():
                return "Template operation completed"
            elif "report" in tool_name.lower():
                return "Report generated"
            return "RadLex operation completed"

        # FHIR tools
        elif tool_name.startswith("fhir."):
            resource_type = result.get("resourceType", "unknown")
            if resource_type == "Bundle":
                entry_count = len(result.get("entry", []))
                return f"Bundle with {entry_count} entries"
            elif resource_type != "unknown":
                resource_id = result.get("id", "no-id")
                return f"{resource_type} (id: {resource_id})"
            return "FHIR operation completed"

        # Utils tools (DICOM parsing)
        elif tool_name == "utils.parse_dicom":
            if result.get("is_valid"):
                tags = result.get("tags", {})
                modality = tags.get("Modality", "unknown")
                body_part = tags.get("BodyPartExamined", "unknown")
                num_tags = result.get("num_tags", 0)
                return f"DICOM parsed: {modality}, {body_part}, {num_tags} tags"
            return f"DICOM invalid: {result.get('error', 'unknown error')}"

        elif tool_name == "utils.parse_dicom_directory":
            total = result.get("total_files", 0)
            num_series = result.get("num_series", 0)
            return f"Directory parsed: {total} files, {num_series} series"

        # Generic fallback
        if result.get("status"):
            return f"Status: {result['status']}"
        if result.get("error"):
            return f"Error: {result['error']}"
        return "completed"

    def _extract_answer_from_results(self, agent_response: str, execution_history: List[Dict], final_result: Any) -> str:
        """Extract meaningful answer from agent response and execution results"""
        agent_text = agent_response.strip()

        # Build response with tool results
        response_parts = []

        # Add agent's text if it's more than just GOAL_ACHIEVED
        clean_text = agent_text.replace("GOAL_ACHIEVED", "").replace("GOAL ACHIEVED", "").strip()
        if clean_text and len(clean_text) > 20:
            response_parts.append(clean_text)

        # Add results from successful tool executions
        for event in execution_history:
            if event.get('success') and event.get('result'):
                tool_name = event.get('tool', 'unknown')
                result = event['result']

                # Format result based on tool type
                if tool_name == "monai.list_models" and isinstance(result, dict):
                    models = result.get('models', [])
                    if models:
                        response_parts.append(f"\n**Available Models ({len(models)} total):**")
                        for m in models:
                            status = "✓ downloaded" if m.get('downloaded') else "○ not downloaded"
                            response_parts.append(f"- **{m.get('name')}** ({m.get('modality', '?')}, {m.get('body_part', '?')}) - {status}")

                elif tool_name == "radlex.list_templates" and isinstance(result, dict):
                    templates = result.get('templates', [])
                    if templates:
                        response_parts.append(f"\n**Available Templates ({len(templates)} total):**")
                        for t in templates:
                            response_parts.append(f"- **{t.get('name')}** ({t.get('modality', '?')}, {t.get('body_part', '?')})")

                elif tool_name == "fhir.search" and isinstance(result, dict):
                    entries = result.get('entry', [])
                    response_parts.append(f"\n**Search Results ({len(entries)} found):**")
                    for entry in entries[:5]:  # Limit to 5
                        resource = entry.get('resource', {})
                        response_parts.append(f"- {resource.get('resourceType', '?')} (ID: {resource.get('id', '?')})")

                elif isinstance(result, dict) and 'error' not in result:
                    # Generic result summary
                    summary = event.get('result_summary', '')
                    if summary and summary != 'completed':
                        response_parts.append(f"\n{tool_name}: {summary}")

        if response_parts:
            return "\n".join(response_parts)

        return "Task completed successfully."


# Global agent instance
agent_decision = AgenticAgent()

if __name__ == "__main__":
    import asyncio
    async def main():
        await agent_decision._initialize_components()
        # ... add your main agent logic here ...

        result = await agent_decision.execute_task("List all existing models in MONAI Model Zoo.")
        print(f"Final Result: {result}")

        await agent_decision.close()
    asyncio.run(main())
