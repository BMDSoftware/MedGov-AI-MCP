#!/usr/bin/env python3
from ast import Set
import os
import json
from re import S
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

import yaml

from tool_registry import ToolRegistry


class SessionContext:
    """Accumulates structured tool results across queries so the agent has memory."""

    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self.current_patient: Optional[Dict] = None
        self._max_entries = 50

    def record(self, tool_name: str, result_summary: str, key_data: Dict[str, Any]):
        """Store a condensed record of a successful tool execution."""
        self.entries.append({
            "tool": tool_name,
            "summary": result_summary,
            "data": key_data,
            "timestamp": datetime.now().isoformat()
        })
        if len(self.entries) > self._max_entries:
            self.entries = self.entries[-self._max_entries:]

    def build_context_string(self) -> str:
        """Build a concise text block to inject into prompts."""
        if not self.entries:
            return ""

        lines = ["# SESSION CONTEXT (previous interactions this session)"]
        for i, entry in enumerate(self.entries, 1):
            lines.append(f"{i}. [{entry['tool']}] {entry['summary']}")
            if entry["data"]:
                for k, v in entry["data"].items():
                    if v is None:
                        continue
                    val_str = str(v)
                    if len(val_str) > 200:
                        val_str = val_str[:200] + "..."
                    lines.append(f"   {k}: {val_str}")
        return "\n".join(lines)

    def clear(self):
        """Reset all session context."""
        self.entries.clear()
        self.current_patient = None

    def set_patient(self, patient_id: str, patient_name: str):
        """Set patient focus. Clears context if patient changes."""
        if self.current_patient and self.current_patient["id"] != patient_id:
            self.clear()
        self.current_patient = {"id": patient_id, "name": patient_name}

# LLM Backend selection: "ollama" (local) or "gemini" (API)
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")

SKILL_DIR_PATH = Path(__file__).parent / "skills"

# NOTE: Guided workflow removed - now using true agentic approach
# The LLM (Gemini or Ollama) decides which tools to call based on context
# Keeping this comment for future reference if deterministic mode is needed
# WORKFLOW_STEPS = [
#     {"name": "analyze", "tool": "monai.analyze_image", "required": True},
#     {"name": "list", "tool": "monai.list_models", "required": True},
#     {"name": "download", "tool": "monai.download_model", "required": False},
#     {"name": "inference", "tool": "monai.run_inference", "required": True},
# ]


class AgenticAgent:
    """AI agent that decides which MCP tools to call based on context and data"""

    def __init__(self, callback=None):
        self.tool_registry = ToolRegistry()
        self.available_tools = {}
        self.agent_tools: Set[str] = set()
        self.callback = callback  # Callback function for real-time event tracking
        self.llm_client = None
        self.session_context = SessionContext()  # Persists tool results across queries
        self.require_confirmation = True  # Require user confirmation before tool execution
        self.pending_tool_call = None  # Stores tool call waiting for confirmation
        self.pending_task_context = None  # Stores context for resuming after confirmation
        # Use async init pattern for tool discovery
        # You must call await self._initialize_components() after instantiation

    async def _initialize_components(self):
        """Initialize LLM client and tool registry with discovered tools"""
        self.available_tools = await self.tool_registry.discover_tools()
        self.agent_tools = set(self.available_tools.keys())
        skills = self.load_all_skills()
        enabled_tools = self.get_enabled_agent_tools()
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

        patient_prompt = f"""
# ROLE
You are a specialized Healthcare AI Assistant. Your operations are strictly bound to the medical context of the current patient.

# PATIENT CONTEXT
- **Name:** {patient_name}
- **Patient ID:** {patient_id}

# AVAILABLE SKILLS (DIRECTORY)
{self.load_all_skills()}

# SKILL USAGE PROTOCOL (PROGRESSIVE DISCLOSURE)
You do not have all instructions loaded into your memory at once. You must follow this tiered workflow:

1. **DISCOVERY (Current State):** You can see the "Available Skills" list above. If a user asks "What can you do?", explain these skills based on their descriptions. Do NOT call a tool just to list them.
2. **READ SKILL:** When a task requires a specific skill, call `skills.read_skill_file(skill_name)` to get the detailed instructions and rules (SKILL.md) for that domain.
3. **EXPLORE REFERENCES:** If you need deeper technical details or schemas mentioned in the SKILL.md, first use `skills.list_skill_files(skill_name)` to see available files, then use `skills.read_references(skill_name, file_path)` to read specific reference files.
4. **EXECUTE:** After reading the skill instructions, proceed to use the specific domain tools (e.g., `monai.*`, `fhir.*`). If the skill has executable scripts, use `skills.execute_script(skill_name, script_name, parameters)`.

# OPERATIONAL RULES
- **One at a Time:** Work with only one skill at a time. 
- **Tool Reasoning:** Before calling any tool, you must state: "I am using [tool_name] because [reasoning related to patient {patient_id}]."
- **ID Verification:** Every time a tool returns data, verify that the Patient ID in the data matches "{patient_id}". If there is a mismatch, stop and alert the user immediately.
- **No Hallucinations:** If you do not have a skill that matches the user's request, state: "I do not have the specific clinical skill required for this task." Do not attempt to guess or simulate skill outputs.
- **Independence:** Skills are external resources. Treat their outputs as clinical observations that require your professional interpretation.

# INTERACTION GUIDELINES
- **If the user asks for information/capabilities:** Read from the "Available Skills" list above and describe them.
- **If the user requests a clinical action (e.g., "Analyze the labs"):** 
    1. Identify the correct skill from the directory.
    2. Call `skills.read_skill_file(skill_name)`.
    3. Follow the instructions returned by that tool to complete the request.

# EMERGENCY & SAFETY
If the patient's data appears critical or the tools return error codes, prioritize clear communication of the status over performing complex analysis."""
        
        if self.llm_client:
            self.llm_client.update_system_prompt(patient_prompt)
        self.session_context.set_patient(patient_id, patient_name)

    def reset_session_context(self):
        """Clear all accumulated session context."""
        self.session_context.clear()
        print("Session context cleared.")

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
    

    async def confirm_tool_execution(self) -> Optional[Dict]:
        """Execute the pending tool after user confirmation"""
        if not self.pending_tool_call:
            return {"error": "No pending tool call to confirm"}

        pending = self.pending_tool_call
        self.pending_tool_call = None

        # Execute the tool
        tool_name = pending["tool_name"]
        arguments = pending["arguments"]
        print(f"Confirmed - Executing: {tool_name}")

        result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)

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
            self.session_context.record(tool_name, result_summary, key_data)
            print(f"Tool succeeded: {result_summary}")
        else:
            error_msg = result.get("error") if result else "No result"
            execution_history.append({
                "tool": tool_name,
                "success": False,
                "error": error_msg
            })
            print(f"Tool failed: {error_msg}")

        # Continue the task from where we left off
        return await self.execute_task(
            goal=pending["goal"],
            data=pending["data"],
            imageList=pending["imageList"],
            max_iterations=pending["max_iterations"] - pending["iterations_used"],
            metadata=pending["metadata"],
            _resume_history=execution_history
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

    async def execute_task(self, goal: str, data: Any = None, imageList: Any = None, max_iterations: int = 20, metadata: Dict = None, _resume_history: List = None) -> Optional[Dict]:
        """
        Truly autonomous task execution - agent reasons about tools and executes

        Args:
            goal: Natural language description of what to accomplish
            data: Optional data context (e.g., patient data to save)
            imageList: Optional list of images for processing
            max_iterations: Maximum number of tool executions allowed
            metadata: Optional dict with modality, body_part for filtering models

        Returns:
            Final result if successful, None if goal not achieved
        """
        print(f"Starting autonomous task: {goal}")
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
                # Build context with execution history including MCP responses
                history_text = ""
                if execution_history:
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
                            history_text += f"Failed: {event.get('error', 'Unknown error')}"
                        history_text += "\n"
                
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

                if not execution_history:
                    # First iteration - include session context so agent knows what happened before
                    prompt = f"""GOAL: {goal}{data_context}{image_context}{session_block}

Analyze the goal and decide your next action."""
                else:
                    # Subsequent iterations - evaluate previous result
                    last_event = execution_history[-1]
                    prompt = f"""GOAL: {goal}{data_context}{image_context}
{history_text}

The last tool returned: {last_event.get('result_summary', 'a result')}

Does this accomplish the goal?
- If YES: Respond with explicitaly "GOAL_ACHIEVED" and provide the final result
- If NO: Take the next action
- If you need more information to proceed, say "NEED MORE INFO" and specify what you need.

Your decision:"""

                print(f"Prompt: {prompt}")
                
                # Prepare content with actual images for Gemini
                content_parts = [prompt]
                
                response = self.llm_client.generate_content(content_parts, images_for_llm)
                print(f"Response: {response}")
                
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

                            # Check if confirmation is required
                            if self.require_confirmation:
                                print(f"Tool confirmation required: {tool_name}")
                                self.pending_tool_call = {
                                    "tool_name": tool_name,
                                    "arguments": arguments,
                                    "goal": goal,
                                    "execution_history": execution_history,
                                    "imageList": imageList,
                                    "data": data,
                                    "metadata": metadata,
                                    "iterations_used": iterations,
                                    "max_iterations": max_iterations
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

                            result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)

                            # Check if result contains an error
                            is_error = False
                            if isinstance(result, dict):
                                is_error = result.get("is_error") or result.get("error") or "error" in str(result.get("text", "")).lower()

                            # Record execution with result details
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
                                self.session_context.record(tool_name, result_summary, key_data)

                                final_result = result
                                print(f"Tool succeeded: {result_summary}")
                            elif result and is_error:
                                error_msg = result.get("error") or result.get("text") or "Unknown error"
                                execution_history.append({
                                    "tool": tool_name,
                                    "success": False,
                                    "error": error_msg,
                                    "result": result
                                })
                                print(f"Tool failed: {error_msg}")
                            else:
                                execution_history.append({
                                    "tool": tool_name,
                                    "success": False,
                                    "error": "Execution returned no result"
                                })
                                print(f"Tool execution failed")
                
                # If agent responded with text but no tool call
                if has_text and not has_function_call:
                    text_response = response.text.strip()
                    # Check if it's a GOAL_ACHIEVED response
                    if "GOAL_ACHIEVED" in text_response.upper() or "GOAL ACHIEVED" in text_response.upper():
                        pass  # Already handled above
                    # Check if this is a valid conversational response (no successful tools, or no tools at all)
                    elif not execution_history or all(not e.get('success') for e in execution_history):
                        # No successful tool calls - accept text response if it's substantial
                        if len(text_response) > 20:  # More than a short error
                            print(f"Agent responded with text (no tools needed for this query)")
                            return {
                                "type": "agent_response",
                                "answer": text_response,
                                "tools_used": [],
                                "execution_history": execution_history,
                                "success": True
                            }
                        else:
                            print(f"Agent response too short, continuing...")
                            execution_history.append({
                                "tool": "none",
                                "success": False,
                                "error": "Agent response was not actionable"
                            })
                    else:
                        # Agent has successful history but didn't declare GOAL_ACHIEVED
                        print(f"Agent didn't declare goal achieved despite successful tools")
                        execution_history.append({
                            "tool": "none",
                            "success": False,
                            "error": "Agent did not declare GOAL_ACHIEVED"
                        })
                    
            except Exception as e:
                print(f"Error in agentic workflow: {type(e).__name__}: {e}")
                execution_history.append({
                    "tool": None,
                    "success": False,
                    "error": str(e),
                    "result": None
                })
        print("Max iterations reached or goal not achieved.")
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
