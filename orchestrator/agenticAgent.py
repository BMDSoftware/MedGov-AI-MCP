#!/usr/bin/env python3
from ast import Set
import os
import json
from re import S
from typing import Dict, List, Optional, Any
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

class AgenticAgent:
    """AI agent that decides which MCP tools to call based on context and data"""

    def __init__(self, callback=None, enable_debug_logging=True, log_level=logging.DEBUG):
        self.tool_registry = ToolRegistry()
        self.available_tools = {}
        self.agent_tools: Set[str] = set()
        self.callback = callback  # Callback function for real-time event tracking
        self.llm_client = None
        self.session_context = SessionContext()  # Persists tool results across queries
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

    def enable_tool(self, tool_name: str):
        if tool_name in self.available_tools and tool_name not in self.agent_tools:
            self.agent_tools.add(tool_name)
            self._refresh_agent_components()
        elif tool_name in self.agent_tools:
            print(f"Tool already enabled: {tool_name}")
        else:
            print(f"Tool not found in available_tools: {tool_name}")

    def disable_tool(self, tool_name: str):
        if tool_name in self.agent_tools:
            self.agent_tools.remove(tool_name)
            self._refresh_agent_components()
        else:
            print(f"Tool not enabled: {tool_name}")

    def _refresh_agent_components(self):
        enabled_tools = self.get_enabled_agent_tools()
        if self.llm_client:
            self.llm_client.update_tools(enabled_tools)

    def set_patient_focus(self, patient_id: str, patient_name: str):
        """Set the agent to focus on a specific patient for healthcare conversations"""

        # # Old skills-based patient prompt:
        # patient_prompt = f"""
        # # ROLE
        # You are a specialized Healthcare AI Assistant. Your operations are strictly bound to the medical context of the current patient.
        # # PATIENT CONTEXT
        # - **Name:** {patient_name}
        # - **Patient ID:** {patient_id}
        # # AVAILABLE SKILLS (DIRECTORY)
        # {self.load_all_skills()}
        # # SKILL USAGE PROTOCOL (PROGRESSIVE DISCLOSURE)
        # ... (progressive disclosure workflow removed - agent now uses MCP tools directly)
        # """

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
2. NEVER invent file paths. If a tool needs a file path, use the one from "IMAGES AVAILABLE" in the context. If none is available, ask the user to upload or provide one.
3. For DICOM files (.dcm): parse the metadata first to extract modality and body part before selecting models or running inference.
4. MONAI models require 3D volumes (.nii, .nii.gz). If the image is a single 2D slice, inform the user.
5. Do not repeat a tool call that already failed. Explain the error and ask how to proceed.
6. After a tool returns results, summarize them clearly for the user."""
        
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
        
        self.logger.info(f"\nTOOL CONFIRMATION APPROVED:")
        self.logger.info(f"  Tool: {tool_name}")
        self.logger.info(f"  User confirmed execution")
        self.logger.info(f"\nTOOL CALL REQUESTED:")
        self.logger.info(f"  Tool: {tool_name}")
        self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")

        result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)
        
        self.logger.info(f"\nTOOL RESULT:")
        self.logger.info(f"  Tool: {tool_name}")
        result_full = json.dumps(result, indent=4) if isinstance(result, dict) else str(result)
        self.logger.info(f"  Result: {result_full}")

        # Check if result contains an error
        is_error = False
        if isinstance(result, dict):
            is_error = result.get("is_error") or result.get("error")

        execution_history = pending["execution_history"]

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
            
            self.logger.info(f"  Status: SUCCESS")
            self.logger.info(f"  Summary: {result_summary}")
            
            # Send tool result back to LLM (Gemini only)
            # For Ollama: Skip this, execution history will be in the next prompt
            is_gemini = LLM_BACKEND.lower() != "ollama"
            
            if is_gemini:
                self.logger.info(f"\nSENDING FULL RESULT TO LLM via function_response")
                llm_response = self.llm_client.send_function_response(tool_name, result)
                self.logger.info(f"Captured LLM response from send_function_response (Gemini)")
            else:
                llm_response = None
        else:
            error_msg = result.get("error") if result else "No result"
            execution_history.append({
                "tool": tool_name,
                "success": False,
                "error": error_msg
            })
            print(f"Tool failed: {error_msg}")
            
            self.logger.error(f"  Status: FAILED")
            self.logger.error(f"SENDING ERROR TO LLM via function_response")
            self.logger.error(f"  Error: {error_msg}")
            
            # Send error back to LLM (Gemini only)
            # For Ollama: Skip this, execution history will be in the next prompt
            is_gemini = LLM_BACKEND.lower() != "ollama"
            
            if is_gemini:
                llm_response = self.llm_client.send_function_response(tool_name, error_msg)
                self.logger.info(f"Captured LLM response from send_function_response (Gemini)")
            else:
                llm_response = None

        # Continue the task from where we left off
        # Only pass _resume_response if using Gemini
        return await self.execute_task(
            goal=pending["goal"],
            data=pending["data"],
            imageList=pending["imageList"],
            max_iterations=pending["max_iterations"] - pending["iterations_used"],
            metadata=pending["metadata"],
            session_id=pending.get("session_id"),
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

    # NOTE: Guided workflow methods commented out - using true agentic approach now
    # Keeping for future reference if deterministic mode is needed
    #
    # def _get_workflow_state(self, execution_history: List[Dict], metadata: Dict = None) -> Dict:
    #     """Analyze execution history to determine workflow state"""
    #     state = {
    #         "analyze_done": False,
    #         "list_done": False,
    #         "download_done": False,
    #         "inference_done": False,
    #         "image_path": None,
    #         "model_name": None,
    #         "model_downloaded": False,
    #         "inference_result": None,
    #         "detected_modality": None,
    #         "body_part": metadata.get("body_part") if metadata else None,
    #     }
    #     for event in execution_history:
    #         if not event.get("success"):
    #             continue
    #         tool = event.get("tool", "")
    #         result = event.get("result", {})
    #         if tool == "monai.analyze_image":
    #             state["analyze_done"] = True
    #             if isinstance(result, dict):
    #                 state["image_path"] = result.get("path") or result.get("file_path")
    #                 analysis = result.get("analysis", {})
    #                 modalities = analysis.get("detected_modalities", [])
    #                 if modalities:
    #                     state["detected_modality"] = modalities[0]
    #         elif tool == "monai.list_models":
    #             state["list_done"] = True
    #             if isinstance(result, dict):
    #                 models = result.get("models", [])
    #                 for model in models:
    #                     if model.get("downloaded"):
    #                         state["model_downloaded"] = True
    #                         state["model_name"] = model.get("name")
    #                         break
    #                 if not state["model_name"] and models:
    #                     state["model_name"] = models[0].get("name")
    #         elif tool == "monai.download_model":
    #             state["download_done"] = True
    #             state["model_downloaded"] = True
    #             if isinstance(result, dict) and result.get("model_name"):
    #                 state["model_name"] = result.get("model_name")
    #         elif tool == "monai.run_inference":
    #             state["inference_done"] = True
    #             state["inference_result"] = result
    #     return state
    #
    # def _get_next_workflow_step(self, state: Dict, image_path: str) -> Optional[Dict]:
    #     """Determine the next tool to call based on workflow state"""
    #     if not state["analyze_done"]:
    #         return {"tool_name": "monai.analyze_image", "arguments": {"path": image_path}}
    #     if not state["list_done"]:
    #         args = {}
    #         if state.get("detected_modality"):
    #             args["modality"] = state["detected_modality"]
    #         if state.get("body_part"):
    #             args["body_part"] = state["body_part"]
    #         return {"tool_name": "monai.list_models", "arguments": args}
    #     if state["model_name"] and not state["model_downloaded"]:
    #         return {"tool_name": "monai.download_model", "arguments": {"model_name": state["model_name"]}}
    #     if not state["inference_done"] and state["model_name"] and state["model_downloaded"]:
    #         return {"tool_name": "monai.run_inference", "arguments": {"image_path": state["image_path"] or image_path, "model_name": state["model_name"]}}
    #     return None

    async def execute_task(self, goal: str, data: Any = None, imageList: Any = None, max_iterations: int = 20, metadata: Dict = None, _resume_history: List = None, _resume_response: Optional[Any] = None, session_id: str = None) -> Optional[Dict]:
        """
        Truly autonomous task execution - agent reasons about tools and executes

        Args:
            goal: Natural language description of what to accomplish
            data: Optional data context (e.g., patient data to save)
            imageList: Optional list of images for processing
            max_iterations: Maximum number of tool executions allowed
            metadata: Optional dict with modality, body_part for filtering models
            _resume_history: Optional execution history to resume from
            _resume_response: Optional LLM response to use instead of generating new one

        Returns:
            Final result if successful, None if goal not achieved
        """
        print(f"Starting autonomous task: {goal}")
        self.logger.info("=" * 80)
        self.logger.info(f"TASK START: {goal}")
        self.logger.info(f"Max iterations: {max_iterations}")
        if metadata:
            self.logger.info(f"Metadata: {json.dumps(metadata, indent=2)}")
        if imageList:
            self.logger.info(f"Images provided: {len(imageList)} file(s)")
        if data:
            self.logger.info(f"Data provided: {len(str(data))} chars")
        
        if metadata:
            print(f"Metadata: modality={metadata.get('modality')}, body_part={metadata.get('body_part')}")

        execution_history = _resume_history if _resume_history else []
        iterations = 0
        final_result = None

        # Extract image path for workflow
        image_path = None
        if imageList and isinstance(imageList, list) and imageList:
            image_path = imageList[0][0]  # First image's temp file path
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
                
                image_context = "\n\nIMAGES AVAILABLE: None. User has not uploaded any images."
                images_for_llm = None  # Only pass 2D images to LLM (if supported)

                if imageList:
                    # Handle imageList as (temp_filepath, content) tuples
                    if isinstance(imageList, list) and imageList:
                        temp_files = [temp_filepath for temp_filepath, _ in imageList]
                        image_context = f"\n\nIMAGES AVAILABLE: Yes\nUse these file paths: {', '.join(temp_files)}"

                        # Only pass small 2D images to LLM, skip large 3D medical files
                        images_for_llm = []
                        for temp_filepath, content in imageList:
                            ext = temp_filepath.lower()
                            # Skip 3D formats - too large, LLM can't visualize
                            if not ext.endswith(('.nii', '.nii.gz', '.dcm', '.mha', '.mhd', '.nrrd')):
                                # Only include if file is small enough (< 5MB)
                                if len(content) < 5 * 1024 * 1024:
                                    images_for_llm.append((temp_filepath, content))

                        if not images_for_llm:
                            images_for_llm = None
                    else:
                        image_context = f"\n\nIMAGES AVAILABLE:\nImage data provided"

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
                    self.logger.info(f"\nUSING RESPONSE FROM send_function_response (no redundant prompt)\n")
                    self.logger.info(f"\nLLM RAW RESPONSE:\n{response}\n")
                    
                    print(f"Using response from send_function_response (Gemini optimization)")
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
- If YES: Respond with explicitly "GOAL_ACHIEVED" and provide the final result
- If NO: Call the next tool you need
- If you need more information, say "NEED MORE INFO" and specify what you need.

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
                    print(f"Response: {response}")
                    
                    self.logger.info(f"\nLLM RAW RESPONSE:\n{response}\n")
                
                # Check if agent declares success (text response, no tool call)
                has_text = False
                has_function_call = False
                
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            has_text = True
                            text_content = part.text.strip().upper()
                            if "GOAL_ACHIEVED" in text_content or "GOAL ACHIEVED" in text_content:
                                print(f"Agent declares: Goal achieved!")
                                # Return detailed response with execution history
                                answer = self._extract_answer_from_results(part.text, execution_history, final_result)
                                tools_used = [event['tool'] for event in execution_history if event['success']]
                                
                                self.logger.info(f"\n{'='*60}")
                                self.logger.info(f"TASK COMPLETED SUCCESSFULLY")
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
                                print(f"Agent requests more information to proceed.")
                                return {
                                    "type": "agent_response",
                                    "answer": part.text.strip(),
                                    "tools_used": [],
                                    "execution_history": execution_history,
                                    "success": False
                                }
                                
                        
                        if hasattr(part, 'function_call') and part.function_call:
                            has_function_call = True
                            tool_name = part.function_call.name
                            arguments = dict(part.function_call.args)

                            # Resolve tool name if missing prefix (e.g., "get_capabilities" -> "fhir.get_capabilities")
                            if tool_name not in self.available_tools:
                                for full_name in self.available_tools.keys():
                                    if full_name.endswith(f".{tool_name}"):
                                        print(f"Resolved tool name: {tool_name} -> {full_name}")
                                        tool_name = full_name
                                        break

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
                                    continue

                            # --- Built-in tool intercept ---
                            # Handle built-in tools locally without going to MCP
                            if tool_name == "list_tasks":
                                tasks = db.list_tasks(session_id=session_id)
                                summary = [
                                    {
                                        "id": t["id"][:8],
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
                                if is_gemini:
                                    _resume_response = self.llm_client.send_function_response(tool_name, result)
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
                                if is_gemini:
                                    _resume_response = self.llm_client.send_function_response(tool_name, result)
                                continue

                            # Check if confirmation is required
                            if self.require_confirmation:
                                print(f"Tool confirmation required: {tool_name}")
                                
                                self.logger.info(f"\nTOOL CONFIRMATION REQUIRED:")
                                self.logger.info(f"  Tool: {tool_name}")
                                self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")
                                
                                self.pending_tool_call = {
                                    "tool_name": tool_name,
                                    "arguments": arguments,
                                    "goal": goal,
                                    "execution_history": execution_history,
                                    "imageList": imageList,
                                    "data": data,
                                    "metadata": metadata,
                                    "iterations_used": iterations,
                                    "max_iterations": max_iterations,
                                    "session_id": session_id,
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
                            
                            self.logger.info(f"\nTOOL CALL REQUESTED:")
                            self.logger.info(f"  Tool: {tool_name}")
                            self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")

                            result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)
                            
                            self.logger.info(f"\nTOOL RESULT:")
                            self.logger.info(f"  Tool: {tool_name}")
                            result_full = json.dumps(result, indent=4) if isinstance(result, dict) else str(result)
                            self.logger.info(f"  Result: {result_full}")

                            # Check if result contains an error
                            is_error = False
                            if isinstance(result, dict):
                                is_error = result.get("is_error") or result.get("error") or "error" in str(result.get("text", "")).lower()

                            # Record execution with result details
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
                                
                                self.logger.info(f"  Status: SUCCESS")
                                self.logger.info(f"  Summary: {result_summary}")
                                
                                # Send tool result back to LLM (Gemini only)
                                # For Ollama: Skip this, execution history will be in the next prompt
                                if is_gemini:
                                    self.logger.info(f"\nSENDING FULL RESULT TO LLM via function_response")
                                    _resume_response = self.llm_client.send_function_response(tool_name, result)
                                    self.logger.info(f"Captured response from send_function_response - will use on next iteration")
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
                                
                                # Send error back to LLM (Gemini only)
                                # For Ollama: Skip this, execution history will be in the next prompt
                                if is_gemini:
                                    error_response = {"error": str(error_msg), "is_error": True}
                                    self.logger.info(f"\nSENDING ERROR TO LLM via function_response")
                                    _resume_response = self.llm_client.send_function_response(tool_name, error_response)
                                
                                print(f"Tool failed: {error_msg}")
                                
                                self.logger.error(f"  Status: FAILED")
                                self.logger.error(f"  Error: {error_msg}")
                            else:
                                # Send error back to LLM (Gemini only)
                                # For Ollama: Skip this, execution history will be in the next prompt
                                if is_gemini:
                                    error_response = {"error": "Execution returned no result", "is_error": True}
                                    self.logger.info(f"\nSENDING NO-RESULT ERROR TO LLM via function_response")
                                    _resume_response = self.llm_client.send_function_response(tool_name, error_response)
                                
                                execution_history.append({
                                    "tool": tool_name,
                                    "success": False,
                                    "error": "Execution returned no result"
                                })
                                print(f"Tool execution failed")
                                
                                self.logger.error(f"  Status: FAILED - No result returned")
                
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
                            print(f"Agent explaining tool error to user")
                        else:
                            print(f"Agent responded with text (no tools needed for this query)")
                        tools_used = [event['tool'] for event in execution_history if event.get('success')]
                        return {
                            "type": "agent_response",
                            "answer": text_response,
                            "tools_used": tools_used,
                            "execution_history": execution_history,
                            "success": not last_failed
                        }
                    else:
                        print(f"Agent response too short, continuing...")
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

                print(f"Error in agentic workflow: {type(e).__name__}: {e}")
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
                return f"Template operation completed"
            elif "report" in tool_name.lower():
                return f"Report generated"
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
