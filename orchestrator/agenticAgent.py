#!/usr/bin/env python3
import os
import json
import re
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass, field, asdict

from mem0 import Memory
import mem0
import yaml

from tool_registry import ToolRegistry
from logger import Logger
import task_runner
import database as db
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

config = {
    "llm": {
        "provider": "gemini",
        "config": {
            "model": "gemini-2.0-flash",
            "temperature": 0.2,
            "max_tokens": 2000,
            "top_p": 1.0
        }
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2" # Small, fast, and local
        }
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "path": ".mem0_data" # Saves your memory to a local folder
        }
    }
}

memory = Memory.from_config(config)
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

@dataclass
class PlanStep:
    id: int
    description: str
    status: str = "pending"          # "pending" | "done" | "failed" | "skipped"
    tool_name: Optional[str] = None  # filled by code after execution
    result_summary: Optional[str] = None


@dataclass
class AgentPlan:
    goal: str
    needs_skills: bool = True
    steps: List[PlanStep] = field(default_factory=list)

    def current_step(self) -> Optional[PlanStep]:
        return next((s for s in self.steps if s.status == "pending"), None)

    def mark_done(self, step_id: int, tool_name: str, result_summary: str):
        for s in self.steps:
            if s.id == step_id:
                s.status = "done"
                s.tool_name = tool_name
                s.result_summary = result_summary

    def mark_failed(self, step_id: int, tool_name: str, error: str):
        for s in self.steps:
            if s.id == step_id:
                s.status = "failed"
                s.tool_name = tool_name
                s.result_summary = f"Error: {error}"

    def render(self) -> str:
        icons = {"pending": "[ ]", "done": "[x]", "failed": "[!]", "skipped": "[-]"}
        lines = [f"EXECUTION PLAN — {self.goal}"]
        for s in self.steps:
            line = f"  {icons[s.status]} Step {s.id}: {s.description}"
            if s.result_summary:
                line += f"  → {s.result_summary}"
            lines.append(line)
        return "\n".join(lines)


@dataclass
class AgentState:
    task: str
    completed_steps: List[str] = field(default_factory=list)   # one-sentence per step
    current_objective: str = ""
    artifacts: List[str] = field(default_factory=list)          # file paths only
    important_facts: Dict[str, Any] = field(
        default_factory=lambda: {"task_constraints": {}, "agent_notes": {}}
    )
    status: str = "in_progress"   # in_progress | complete | failed

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class AgenticAgent:
    """AI agent that decides which MCP tools to call based on context and data"""

    _DISABLED_TOOLS_FILE = Path(__file__).parent / "data" / "disabled_tools.json"

    def __init__(self, callback=None, enable_debug_logging=True, log_level=logging.DEBUG):
        self.tool_registry = ToolRegistry()
        self.available_tools = {}
        self.agent_tools: Set[str] = set()
        self.callback = callback  # Callback function for real-time event tracking
        self.llm_client = None
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
        "update_agent_notes": {
            "description": (
                "Store an important finding or fact in your persistent notes for this task. "
                "Use this after any tool returns clinically or technically significant information "
                "you will need later — e.g. detected anatomy, output file paths, model names chosen, "
                "DICOM metadata, or any fact needed to synthesize the final report. "
                "Notes persist across all iterations. Keep values concise (one sentence or short list)."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Short label for this note, e.g. 'spleen_inference_result', 'dicom_modality'.",
                    },
                    "value": {
                        "type": "string",
                        "description": "The fact or finding to remember.",
                    },
                },
                "required": ["key", "value"],
            },
            "server": "__builtin__",
            "original_name": "update_agent_notes",
            "transport": "builtin",
        },
        # Bug 1 fix: explicit completion tool so the LLM never has to say "GOAL_ACHIEVED" in text
        "complete_task": {
            "description": (
                "Call this tool when you have fully completed the task goal and ALL plan steps. "
                "Provide a concise final summary of what was accomplished. "
                "This is the ONLY way to signal task completion — do NOT write 'GOAL_ACHIEVED' in text."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Concise final summary of what was accomplished.",
                    }
                },
                "required": ["summary"],
            },
            "server": "__builtin__",
            "original_name": "complete_task",
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
        try:
            if self._DISABLED_TOOLS_FILE.exists():
                return set(json.loads(self._DISABLED_TOOLS_FILE.read_text()))
        except Exception:
            pass
        return set()

    def _save_disabled_tools(self):
        disabled = set(self.available_tools.keys()) - self.agent_tools
        try:
            self._DISABLED_TOOLS_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._DISABLED_TOOLS_FILE.write_text(json.dumps(list(disabled)))
        except Exception as e:
            print(f"Warning: could not save disabled tools: {e}")

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
6. After a tool returns results, summarize them clearly for the user.
7. MULTI-FILE RULE: When multiple paths are listed in "IMAGES AVAILABLE" and the user asks to analyze or run inference, process ALL of them. Call the appropriate tool for each path one by one. Do not stop after the first.
8. DIRECTORY RULE: A path marked as [DICOM SERIES DIR] is a directory of DICOM slices that forms a single 3D volume. Pass the directory path directly to analyze_image or run_inference — MONAI handles it natively. Do NOT iterate or process individual files inside the directory.
9. NOTE-TAKING: After any tool returns important findings (detected anatomy, output paths, DICOM metadata, chosen model names), call update_agent_notes with a concise key and value. These notes are injected into every subsequent LLM call and help you avoid re-deriving the same information."""
        
        if self.llm_client:
            self.llm_client.update_system_prompt(patient_prompt)


    def _mem0_search(self, query: str, session_id: str) -> str:
        """Search mem0 for relevant memories scoped to this session."""
        print(f"[mem0] Searching for session_id='{session_id}' with query: {query}")
        if not session_id:
            return ""
        try:
            print(f"[mem0] Searching memories for session '{session_id}'...")
            results = memory.search(query, user_id=session_id)
            print(f"[mem0] Raw search result type={type(results).__name__}: {results}")
            items = []
            if isinstance(results, dict):
                items = results.get("results", [])
            elif isinstance(results, list):
                items = results
            if not items:
                print("[mem0] No memories found.")
                return ""
            lines = []
            for m in items:
                if isinstance(m, dict):
                    content = m.get("memory") or m.get("text") or m.get("content")
                    if content:
                        lines.append(f"- {content}")
                else:
                    lines.append(f"- {str(m)}")
            if lines:
                self.logger.info(f"[mem0] Retrieved {len(lines)} memories for session {session_id}")
                return "\n\nSESSION MEMORY (from previous interactions):\n" + "\n".join(lines)
        except Exception as e:
            self.logger.error(f"[mem0] Search failed: {e}")
        return ""

    def _mem0_add(self, fact: str, session_id: str):
        """Store a fact in mem0 scoped to this session."""
        if not session_id or not fact:
            return
        try:
            print(f"[mem0] Adding to memory for session '{session_id}':")
            print(f"[mem0]   Fact: {fact[:300]}{'...' if len(fact) > 300 else ''}")
            result = memory.add(fact, user_id=session_id, infer=True)
            print(f"[mem0] Result: {result}")
            self.logger.info(f"[mem0] Stored memory for session {session_id}")
        except Exception as e:
            print(f"[mem0] Add failed: {e}")
            self.logger.error(f"[mem0] Add failed: {e}")

    def _mem0_store_skill_usage(self, tool_name: str, arguments: dict, result: dict, session_id: str):
        """Store skill name, description, and referenced file in mem0 after a skills tool call."""
        if tool_name == "skills.read_skill_file":
            skill_name = arguments.get("skill_name", "")
            description = ""
            content = result.get("content", "") if isinstance(result, dict) else ""
            if content:
                try:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        metadata = yaml.safe_load(parts[1])
                        description = metadata.get("description", "")
                except Exception:
                    pass
            fact = f"Skill '{skill_name}' was invoked."
            if description:
                fact += f" Description: {description}"

        elif tool_name == "skills.read_references":
            skill_name = arguments.get("skill_name", "")
            file_path = arguments.get("file_path", "")
            fact = f"Reference file '{file_path}' from skill '{skill_name}' was accessed."

        memory.add(fact, user_id=session_id, infer=False)

    

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
    def _mem0_search(self, query: str, session_id: str) -> str:
        """Search mem0 for relevant memories scoped to this session."""
        print(f"[mem0] Searching for session_id='{session_id}' with query: {query}")
        if not session_id:
            return ""
        try:
            print(f"[mem0] Searching memories for session '{session_id}'...")
            results = memory.search(query, user_id=session_id)
            print(f"[mem0] Raw search result type={type(results).__name__}: {results}")
            items = []
            if isinstance(results, dict):
                items = results.get("results", [])
            elif isinstance(results, list):
                items = results
            if not items:
                print("[mem0] No memories found.")
                return ""
            lines = []
            for m in items:
                if isinstance(m, dict):
                    content = m.get("memory") or m.get("text") or m.get("content")
                    if content:
                        lines.append(f"- {content}")
                else:
                    lines.append(f"- {str(m)}")
            if lines:
                self.logger.info(f"[mem0] Retrieved {len(lines)} memories for session {session_id}")
                return "\n\nSESSION MEMORY (from previous interactions):\n" + "\n".join(lines)
        except Exception as e:
            self.logger.error(f"[mem0] Search failed: {e}")
        return ""

    def _mem0_add(self, fact: str, session_id: str):
        """Store a fact in mem0 scoped to this session."""
        if not session_id or not fact:
            return
        try:
            print(f"[mem0] Adding to memory for session '{session_id}':")
            print(f"[mem0]   Fact: {fact[:300]}{'...' if len(fact) > 300 else ''}")
            result = memory.add(fact, user_id=session_id, infer=True)
            print(f"[mem0] Result: {result}")
            self.logger.info(f"[mem0] Stored memory for session {session_id}")
        except Exception as e:
            print(f"[mem0] Add failed: {e}")
            self.logger.error(f"[mem0] Add failed: {e}")

    def _mem0_store_skill_usage(self, tool_name: str, arguments: dict, result: dict, session_id: str):
        """Store skill name, description, and referenced file in mem0 after a skills tool call."""
        if tool_name == "skills.read_skill_file":
            skill_name = arguments.get("skill_name", "")
            description = ""
            content = result.get("content", "") if isinstance(result, dict) else ""
            if content:
                try:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        metadata = yaml.safe_load(parts[1])
                        description = metadata.get("description", "")
                except Exception:
                    pass
            fact = f"Skill '{skill_name}' was invoked."
            if description:
                fact += f" Description: {description}"

        elif tool_name == "skills.read_references":
            skill_name = arguments.get("skill_name", "")
            file_path = arguments.get("file_path", "")
            fact = f"Reference file '{file_path}' from skill '{skill_name}' was accessed."

        memory.add(fact, user_id=session_id, infer=False)

    def _extract_llm_observation(self, response) -> str:
        """Extract the text observation from an LLM response (skips function call parts)."""
        if not response or not response.candidates:
            return ""
        texts = []
        for part in (response.candidates[0].content.parts or []):
            if hasattr(part, 'text') and part.text and part.text.strip():
                texts.append(part.text.strip())
        return " ".join(texts)

    async def refresh_available_tools(self):
        previous_tools = set(self.available_tools.keys())
        previous_enabled = set(self.agent_tools)
        self.available_tools = await self.tool_registry.reload_config_and_refresh()
        self.available_tools.update(self.BUILTIN_TOOLS)
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

        # Retrieve plan state from pending
        _plan: Optional[AgentPlan] = pending.get("plan")
        _state: Optional[AgentState] = pending.get("state")
        _all_results: List[tuple] = list(pending.get("all_results", []))

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
            # Update plan step
            if _plan:
                _step = _plan.current_step()
                if _step:
                    self._update_plan_after_tool(_plan, _step.id, tool_name, True, result_summary)
            _all_results.append((tool_name, confirmed_result))
            if _state:
                self._update_state_after_tool(_state, tool_name, confirmed_result, True, result_summary, _plan)

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
            # Update plan step
            if _plan:
                _step = _plan.current_step()
                if _step:
                    self._update_plan_after_tool(_plan, _step.id, tool_name, False, str(error_msg) if error_msg else "Tool execution failed")
            _all_results.append((tool_name, confirmed_result))
            if _state:
                self._update_state_after_tool(_state, tool_name, confirmed_result, False, str(error_msg) if error_msg else "Tool execution failed", _plan)

        # Build the accumulated results list for this turn:
        # results confirmed so far (from before this call) + this call's result
        turn_accumulated_results = list(pending.get("turn_accumulated_results", [])) + [(tool_name, confirmed_result)]
        turn_remaining_calls = list(pending.get("turn_remaining_calls", []))

        # Process any built-in tools at the front of the remaining calls immediately
        while turn_remaining_calls:
            next_name, next_args = turn_remaining_calls[0]
            if next_name == "list_tasks":
                turn_remaining_calls.pop(0)
                tasks = db.list_tasks(session_id=session_id)
                _summary = [
                    {
                        "id": t["id"][:8],
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
                _body_part = ""
                _modality = ""
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
            elif next_name == "update_agent_notes":
                turn_remaining_calls.pop(0)
                note_key = next_args.get("key", "note")
                note_value = next_args.get("value", "")
                if _state:
                    _state.important_facts["agent_notes"][note_key] = note_value
                    self._prune_agent_notes(_state)
                _result = {"status": "saved", "key": note_key}
                execution_history.append({
                    "tool": next_name,
                    "success": True,
                    "result_summary": f"Saved note: {note_key}",
                    "result": _result,
                })
                turn_accumulated_results.append((next_name, _result))
            elif next_name == "complete_task":
                # Bug 1 fix: drain complete_task in the confirm path too
                turn_remaining_calls.pop(0)
                _summary = next_args.get("summary", "")
                if _state:
                    _state.status = "completed"
                    _state.important_facts["agent_notes"]["final_summary"] = _summary
                _result = {"status": "completed", "summary": _summary}
                execution_history.append({
                    "tool": next_name,
                    "success": True,
                    "result_summary": f"Task completed: {_summary[:80]}",
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
                "imageList": pending["imageList"],
                "data": pending["data"],
                "metadata": pending["metadata"],
                "iterations_used": pending["iterations_used"],
                "max_iterations": pending["max_iterations"],
                "session_id": pending.get("session_id"),
                "turn_accumulated_results": turn_accumulated_results,
                "turn_remaining_calls": turn_remaining_calls,
                "plan": _plan,
                "all_results": list(_all_results),
                "state": _state,
            }
            return {
                "type": "confirmation_required",
                "tool_name": next_name,
                "arguments": next_args,
                "message": f"About to execute: {next_name}",
                "execution_history": execution_history
            }

        # All calls in the turn are resolved — send accumulated results to Gemini

        # Bug 1 fix: if complete_task was called during the drain, return immediately
        if _state and _state.status == "completed":
            final_summary = _state.important_facts["agent_notes"].get("final_summary", "")
            tools_used = [event['tool'] for event in execution_history if event.get('success')]
            self.logger.info("TASK COMPLETED SUCCESSFULLY (via complete_task in confirm drain)")
            return {
                "type": "agent_response",
                "answer": final_summary,
                "tools_used": tools_used,
                "execution_history": execution_history,
                "success": True,
            }

        llm_response = None
        if is_gemini and turn_accumulated_results:
            self.logger.info(f"\nSENDING {len(turn_accumulated_results)} RESULT(S) TO LLM after confirmation")
            try:
                # Bug 1+4 fix: use complete_task instruction; add remaining steps (Bug 4)
                _conf_remaining = [s for s in _plan.steps if s.status == "pending"] if _plan else []
                _conf_remaining_text = ""
                if _conf_remaining:
                    _conf_remaining_text = "\n\nREMAINING PLAN STEPS (not yet completed):\n"
                    _conf_remaining_text += "\n".join(f"  - {s.description}" for s in _conf_remaining)
                goal_check = (
                    f"\n\nORIGINAL GOAL: {pending['goal']}{_conf_remaining_text}\n"
                    "Have ALL plan steps been completed and the goal fully achieved?\n"
                    "- YES (all done) → call complete_task with a concise final summary. Do NOT write 'GOAL_ACHIEVED' in text.\n"
                    "- NO → call the next required tool"
                )
                state_ctx = self._render_state(_state) if _state else ""
                mem0_context_arg = state_ctx + goal_check
                if len(turn_accumulated_results) > 1:
                    llm_response = self.llm_client.send_multiple_function_responses(turn_accumulated_results, mem0_context=mem0_context_arg)
                else:
                    _single_name, _single_data = turn_accumulated_results[0]
                    llm_response = self.llm_client.send_function_response(_single_name, _single_data, mem0_context=mem0_context_arg)
                self.logger.info("Captured LLM response from function_response(s) (Gemini)")


            except Exception as llm_err:
                print(f"LLM API error after tool execution: {type(llm_err).__name__}: {llm_err}")
                return {"error": f"Tool executed but LLM API unreachable: {llm_err}", "is_error": True}

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
            _resume_response=llm_response if is_gemini else None,
            _resume_plan=_plan,
            _resume_last_results=_all_results,
            _resume_state=_state,
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

    # ------------------------------------------------------------------ #
    # Planning helpers                                                     #
    # ------------------------------------------------------------------ #

    def _parse_plan_json(self, raw_text: str) -> Optional[dict]:
        """Three-attempt JSON parser: fenced → first-brace → raw."""
        # Attempt 1: strip ```json ... ``` fences
        fenced = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", raw_text, flags=re.DOTALL).strip()
        try:
            return json.loads(fenced)
        except (json.JSONDecodeError, ValueError):
            pass
        # Attempt 2: extract first {...} block
        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except (json.JSONDecodeError, ValueError):
                pass
        # Attempt 3: direct parse
        try:
            return json.loads(raw_text.strip())
        except (json.JSONDecodeError, ValueError):
            return None

    def _create_execution_plan(self, goal: str, data_context: str, image_context: str) -> Optional[AgentPlan]:
        """Ask Gemini (tool-free) to produce a JSON execution plan for the goal."""
        if not hasattr(self, "llm_client") or self.llm_client is None:
            return None
        if not hasattr(self.llm_client, "genai_client"):
            return None  # Ollama — no planning
        try:
            from google.genai import types as _gtypes
            tool_names = list(self.available_tools.keys())
            skills_text = getattr(self.llm_client, "skills", "") or ""
            skills_block = (
                f"\n\nAVAILABLE SKILLS (use exact names below):\n{skills_text}"
                if skills_text and skills_text != "No skills available"
                else ""
            )
            prompt = (
                f"You are planning the execution of the following medical-AI task.\n\n"
                f"GOAL: {goal}{data_context}{image_context}\n\n"
                f"AVAILABLE TOOLS: {', '.join(tool_names)}{skills_block}\n\n"
                "Produce a JSON execution plan with at most 8 steps. "
                "Return ONLY valid JSON in this exact shape:\n"
                '{"needs_skills": true, "steps": [{"id": 1, "description": "..."}, ...]}\n'
                "Each description should be a concise (~10 word) action statement.\n\n"
                "SKILL STEPS: When a step invokes a clinical skill, write the description as "
                "'Use skill <exact_skill_name>' (e.g. 'Use skill ct_segmentation'). "
                "Do NOT write 'Read skill file' or similar — name the skill directly.\n\n"
                "Set needs_skills=false when the task only requires direct tool calls "
                "(e.g. listing models, checking task status, parsing a DICOM file directly). "
                "Set needs_skills=true when the task requires a clinical workflow skill "
                "(e.g. generating a structured radiology report, running a FHIR workflow, "
                "multi-step protocol that calls skills.read_skill_file)."
            )
            response = self.llm_client.genai_client.models.generate_content(
                model=self.llm_client.model_id,
                contents=prompt,
                config=_gtypes.GenerateContentConfig(temperature=0.0),
            )
            raw = response.text if hasattr(response, "text") else ""
            parsed = self._parse_plan_json(raw)
            if not parsed or "steps" not in parsed:
                self.logger.warning("[plan] Could not parse plan JSON — falling back to no-plan mode")
                return None
            steps = [
                PlanStep(id=s["id"], description=s["description"])
                for s in parsed["steps"]
                if "id" in s and "description" in s
            ]
            if not steps:
                return None
            needs_skills = bool(parsed.get("needs_skills", True))
            plan = AgentPlan(goal=goal, needs_skills=needs_skills, steps=steps)
            self.logger.info(f"[plan] Created plan with {len(steps)} steps")
            return plan
        except Exception as e:
            self.logger.warning(f"[plan] Planning call failed ({type(e).__name__}: {e}) — falling back")
            return None

    # ------------------------------------------------------------------ #
    # AgentState helpers                                                   #
    # ------------------------------------------------------------------ #

    def _init_state(self, goal: str, plan: Optional["AgentPlan"], data: Dict, image_paths: List[str]) -> "AgentState":
        """Create the initial AgentState at task start."""
        first_step = plan.current_step().description if (plan and plan.current_step()) else goal
        constraints = {"patient_data_available": True} if data else {}
        return AgentState(
            task=goal,
            current_objective=first_step,
            artifacts=list(image_paths),
            important_facts={"task_constraints": constraints, "agent_notes": {}},
        )

    def _extract_artifacts(self, result: Any) -> List[str]:
        """Extract absolute file paths from a tool result."""
        result_str = json.dumps(result) if not isinstance(result, str) else result
        found = re.findall(r'(?<!["\w])((?:/[\w.\-_]+)+\.[\w.]{1,6})(?!["\w])', result_str)
        seen: List[str] = []
        for p in found:
            if p not in seen:
                seen.append(p)
        return seen

    def _prune_agent_notes(self, state: "AgentState", budget_tokens: int = 200) -> None:
        """Remove oldest agent_notes entries until under token budget."""
        notes = state.important_facts.get("agent_notes", {})
        while notes and len(json.dumps(notes)) // 4 > budget_tokens:
            oldest_key = next(iter(notes))
            del notes[oldest_key]

    def _update_state_after_tool(
        self,
        state: "AgentState",
        tool_name: str,
        result: Any,
        success: bool,
        summary: str,
        plan: Optional["AgentPlan"],
    ) -> None:
        """Update AgentState after a tool execution."""
        prefix = "Completed" if success else "Failed"
        state.completed_steps.append(f"{prefix}: {tool_name} — {summary}")

        # Extract and deduplicate artifacts
        new_artifacts = self._extract_artifacts(result)
        for a in new_artifacts:
            if a not in state.artifacts:
                state.artifacts.append(a)

        # Advance current objective
        if plan:
            next_step = plan.current_step()
            if next_step:
                state.current_objective = next_step.description

        self._prune_agent_notes(state)

    def _render_state(self, state: "AgentState") -> str:
        """Serialize AgentState to JSON for injection into LLM context."""
        return state.to_json()

    def _build_plan_context(self, plan: Optional[AgentPlan], last_results: list) -> str:
        """Format the plan + recent tool results for injection into mem0_context."""
        if plan is None:
            return ""
        lines = [plan.render()]
        if last_results:
            lines.append("\nRECENT TOOL RESULTS (last 3):")
            for tool_name, result in last_results[-3:]:
                summary = json.dumps(result)
                lines.append(f"  {tool_name}: {summary}")
        return "\n".join(lines)

    def _update_plan_after_tool(
        self,
        plan: Optional[AgentPlan],
        step_id: int,
        tool_name: str,
        success: bool,
        detail: str,
    ):
        """Mark the current plan step done or failed after a tool call."""
        if plan is None:
            return
        if success:
            plan.mark_done(step_id, tool_name, detail)
            self.logger.info(f"[plan] Step {step_id} done via {tool_name}: {detail}")
        else:
            plan.mark_failed(step_id, tool_name, detail)
            self.logger.warning(f"[plan] Step {step_id} failed via {tool_name}: {detail}")

    def _coerce_args(self, args: dict, tool_name: str) -> dict:
        """Bug 2b fix: flatten anyOf schema fragments Gemini sometimes returns as arg values.

        When Gemini misreads an anyOf schema as the arg type, it passes a dict like
        {"anyOf": ["spleen"]} instead of the string "spleen". Detect and unwrap these.
        """
        tool_info = self.available_tools.get(tool_name, {})
        props = tool_info.get("inputSchema", tool_info.get("schema", {})).get("properties", {})
        coerced = {}
        for k, v in args.items():
            expected_type = props.get(k, {}).get("type", "")
            if expected_type == "string" and isinstance(v, dict):
                if "anyOf" in v:
                    candidates = [x for x in v["anyOf"] if isinstance(x, str)]
                    v = candidates[0] if candidates else str(v)
                else:
                    v = str(v)
            coerced[k] = v
        return coerced

    async def execute_task(self, goal: str, data: Any = None, imageList: Any = None, max_iterations: int = 20, metadata: Dict = None, _resume_history: List = None, _resume_response: Optional[Any] = None, session_id: str = None, _resume_plan: Optional[AgentPlan] = None, _resume_last_results: Optional[list] = None, _resume_state: Optional[AgentState] = None) -> Optional[Dict]:
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
        _is_continuation = bool(_resume_history)
        print(f"\n{'='*80}")
        print("Autonomous agent: ", self.is_agent_autonomous)
        print(f"Starting autonomous task: {goal}")
        self.logger.info("=" * 80)
        if _is_continuation:
            self.logger.info(f"TASK CONTINUATION ({max_iterations} iterations remaining): {goal}")
        else:
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
        _inference_queued: set = set()  # Track image paths already queued for inference

        # Reset conversation history for a fresh task (skip on resume to keep tool-use turns)
        is_gemini = LLM_BACKEND.lower() != "ollama"
        if is_gemini and not _resume_history and hasattr(self.llm_client, 'reset_conversation'):
            self.llm_client.reset_conversation()

        # --- Plan-as-STM: create (or resume) an execution plan ---
        # data_context / image_context aren't built yet here, so we pass empty strings;
        # the planning call will re-read the goal for structure.  Full context is
        # injected into every subsequent LLM call via _build_plan_context().
        plan: Optional[AgentPlan] = _resume_plan
        if is_gemini and not _resume_history and plan is None:
            # Build a quick data/image summary for the planner
            _plan_data_ctx = ""
            if data:
                _plan_data_ctx = f"\n\nDATA AVAILABLE:\n{json.dumps(data, indent=2)[:500]}"
            _plan_img_ctx = ""
            if imageList:
                _plan_img_ctx = "\n\nIMAGES AVAILABLE: Yes"
            plan = self._create_execution_plan(goal, _plan_data_ctx, _plan_img_ctx)
        _all_results: List[tuple] = list(_resume_last_results or [])

        # Gate skill tools based on plan.needs_skills (Gemini only, fresh tasks)
        if is_gemini and not _resume_history:
            _all_skill_tools = [t for t in self.available_tools if t.startswith("skills.")]
            # Always restore first (in case previous task disabled them)
            for t in _all_skill_tools:
                self.agent_tools.add(t)
            if plan is not None and not plan.needs_skills:
                for t in _all_skill_tools:
                    self.agent_tools.discard(t)
                self._refresh_agent_components()
                self.logger.info(f"[skills] Disabled {len(_all_skill_tools)} skill tools (task: {goal[:60]})")
            elif plan is not None and plan.needs_skills:
                self._refresh_agent_components()
                self.logger.info(f"[skills] Skill tools active for this task")

        # Init / resume AgentState
        state: Optional[AgentState] = _resume_state
        if is_gemini and not _resume_history and state is None:
            _img_paths = [p for p, _ in (imageList or [])]
            _data_dict = data if isinstance(data, dict) else {}
            state = self._init_state(goal, plan, _data_dict, _img_paths)

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
                        # Separate files and directories so the LLM knows which is which
                        file_paths = []
                        dir_paths = []
                        for temp_filepath, _ in imageList:
                            if os.path.isdir(temp_filepath):
                                dir_paths.append(temp_filepath)
                            else:
                                file_paths.append(temp_filepath)

                        parts = []
                        if file_paths:
                            parts.append("Files: " + ", ".join(file_paths))
                        if dir_paths:
                            parts.append("DICOM series directories (treat each as a single 3D volume — use the directory path directly): " + ", ".join(f"[DICOM SERIES DIR] {p}" for p in dir_paths))
                        image_context = "\n\nIMAGES AVAILABLE: Yes\n" + "\n".join(parts)

                        # Only pass small 2D images to LLM, skip large 3D medical files and directories
                        images_for_llm = []
                        for temp_filepath, content in imageList:
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
                        image_context = "\n\nIMAGES AVAILABLE:\nImage data provided"


                # Check if we're using Gemini and have a response from previous send_function_response
                is_gemini = LLM_BACKEND.lower() != "ollama"
                
                _from_resume = False
                if is_gemini and _resume_response is not None:
                    # Gemini optimization: Use the response we already got from send_function_response
                    response = _resume_response
                    _resume_response = None  # Clear for next iteration
                    _from_resume = True
                    
                    self.logger.info(f"\n{'='*60}")
                    self.logger.info(f"ITERATION {iterations}/{max_iterations}")
                    self.logger.info(f"{'='*60}")
                    self.logger.info("\nUSING RESPONSE FROM send_function_response (no redundant prompt)\n")
                    self.logger.info(f"\nLLM RAW RESPONSE:\n{response}\n")
                    
                    print("Using response from send_function_response (Gemini optimization)")
                else:
                    # Standard flow: prompt the LLM (always for Ollama, or first iteration for Gemini)
                    if not execution_history:
                        # First iteration - include plan as structured context
                        session_context = ("\n\n" + plan.render()) if plan else ""
                        prompt = f"""GOAL: {goal}{data_context}{image_context}{session_context}

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
                        
                        # Bug 3b+4 fix: include current state and remaining steps in the prompt
                        _state_text = f"\n\nCURRENT TASK STATE:\n{self._render_state(state)}" if state else ""
                        _ol_remaining = [s for s in plan.steps if s.status == "pending"] if plan else []
                        _ol_remaining_text = ""
                        if _ol_remaining:
                            _ol_remaining_text = "\n\nREMAINING PLAN STEPS (not yet completed):\n"
                            _ol_remaining_text += "\n".join(f"  - {s.description}" for s in _ol_remaining)
                        prompt = f"""{history_text}
GOAL: {goal}{_state_text}{_ol_remaining_text}

Have ALL plan steps been completed and the goal fully achieved?
- If YES: call complete_task with a concise final summary. Do NOT write "GOAL_ACHIEVED" in text.
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

                    _prompt_plan_ctx = self._render_state(state) if state else ""
                    response = self.llm_client.generate_content(content_parts, images_for_llm, mem0_context=_prompt_plan_ctx)
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
                            text_content = part.text.strip()
                            # Bug 1 fix (Step D): only treat as GOAL_ACHIEVED if it appears at the very start
                            # of the response (anchored regex) to avoid false triggers from echoed prompts.
                            if re.match(r"^\s*GOAL[_\s]ACHIEVED", text_content, re.IGNORECASE):
                                print("Agent declares: Goal achieved! (text fallback)")
                                # Return detailed response with execution history
                                answer = self._extract_answer_from_results(part.text, execution_history, final_result)
                                tools_used = [event['tool'] for event in execution_history if event['success']]

                                if state:
                                    state.status = "completed"

                                self.logger.info(f"\n{'='*60}")
                                self.logger.info("TASK COMPLETED SUCCESSFULLY (text fallback)")
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
                                print("Agent requests more information to proceed.")
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
                            # Bug 2b fix: coerce dict-valued args that Gemini filled with schema fragments
                            _raw_args = self._coerce_args(_raw_args, _raw_name)
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

                    if tool_name == "update_agent_notes":
                        note_key = arguments.get("key", "note")
                        note_value = arguments.get("value", "")
                        if state:
                            state.important_facts["agent_notes"][note_key] = note_value
                            self._prune_agent_notes(state)
                        result = {"status": "saved", "key": note_key}
                        result_summary = f"Saved note: {note_key}"
                        execution_history.append({
                            "tool": tool_name,
                            "success": True,
                            "result_summary": result_summary,
                            "result": result,
                        })
                        final_result = result
                        _turn_results.append((tool_name, result))
                        continue

                    # Bug 1 fix (Step B): complete_task signals explicit task completion
                    if tool_name == "complete_task":
                        summary = arguments.get("summary", "")
                        if state:
                            state.status = "completed"
                            state.important_facts["agent_notes"]["final_summary"] = summary
                        result = {"status": "completed", "summary": summary}
                        execution_history.append({
                            "tool": tool_name,
                            "success": True,
                            "result_summary": f"Task completed: {summary[:80]}",
                            "result": result,
                        })
                        _turn_results.append((tool_name, result))
                        continue

                    # run_inference always runs in the background so the user
                    # can keep chatting and the result lands in the Results tab.
                    if tool_name == "monai.run_inference" and not self.is_agent_autonomous:
                        image_path = arguments.get("image_path", "")
                        model_name = arguments.get("model_name", "")
                        # Pull body_part/modality from LLM arguments (optional display metadata)
                        body_part = arguments.get("body_part", "")
                        modality = arguments.get("modality", "")

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
                            "imageList": imageList,
                            "data": data,
                            "metadata": metadata,
                            "iterations_used": iterations,
                            "max_iterations": max_iterations,
                            "session_id": session_id,
                            "turn_accumulated_results": list(_turn_results),
                            "turn_remaining_calls": _remaining_calls,
                            "plan": plan,
                            "all_results": list(_all_results),
                            "state": state,
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
                        _all_results.append((tool_name, result))
                        # Update plan: mark current pending step done
                        if plan:
                            _step = plan.current_step()
                            if _step:
                                self._update_plan_after_tool(plan, _step.id, tool_name, True, result_summary)
                        if state:
                            self._update_state_after_tool(state, tool_name, result, True, result_summary, plan)

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
                        _all_results.append((tool_name, error_response))
                        if plan:
                            _step = plan.current_step()
                            if _step:
                                self._update_plan_after_tool(plan, _step.id, tool_name, False, str(error_msg))
                        if state:
                            self._update_state_after_tool(state, tool_name, error_response, False, str(error_msg), plan)

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
                        _all_results.append((tool_name, error_response))
                        if plan:
                            _step = plan.current_step()
                            if _step:
                                self._update_plan_after_tool(plan, _step.id, tool_name, False, "Execution returned no result")
                        if state:
                            self._update_state_after_tool(state, tool_name, error_response, False, "Execution returned no result", plan)

                # --- Bug 1 fix (Step C): check if LLM called complete_task this turn ---
                if state and state.status == "completed":
                    final_summary = state.important_facts["agent_notes"].get("final_summary", "")
                    tools_used = [event['tool'] for event in execution_history if event.get('success')]
                    self.logger.info(f"\n{'='*60}")
                    self.logger.info("TASK COMPLETED SUCCESSFULLY (via complete_task)")
                    self.logger.info(f"  Iterations used: {iterations}")
                    self.logger.info(f"  Tools used: {tools_used}")
                    self.logger.info(f"  Summary: {final_summary}")
                    self.logger.info(f"{'='*80}\n")
                    return {
                        "type": "agent_response",
                        "answer": final_summary,
                        "tools_used": tools_used,
                        "execution_history": execution_history,
                        "success": True,
                    }

                # --- Phase 3: send ALL accumulated results to Gemini in one message ---
                # For Ollama: skip this entirely — execution history goes into the next prompt
                if is_gemini and _turn_results:
                    # Bug 1+4 fix: replace "GOAL_ACHIEVED" text with complete_task call instruction;
                    # also list remaining plan steps so LLM knows what's still pending (Bug 4).
                    _remaining = [s for s in plan.steps if s.status == "pending"] if plan else []
                    _remaining_text = ""
                    if _remaining:
                        _remaining_text = "\n\nREMAINING PLAN STEPS (not yet completed):\n"
                        _remaining_text += "\n".join(f"  - {s.description}" for s in _remaining)
                    goal_check = (
                        f"\n\nORIGINAL GOAL: {goal}{_remaining_text}\n"
                        "Have ALL plan steps been completed and the goal fully achieved?\n"
                        "- YES (all done) → call complete_task with a concise final summary. Do NOT write 'GOAL_ACHIEVED' in text.\n"
                        "- NO → call the next required tool"
                    )
                    state_ctx = self._render_state(state) if state else ""
                    mem0_context_arg = state_ctx + goal_check
                    if len(_turn_results) > 1:
                        self.logger.info(f"\nSENDING {len(_turn_results)} RESULTS TO LLM via send_multiple_function_responses")
                        _resume_response = self.llm_client.send_multiple_function_responses(_turn_results, mem0_context=mem0_context_arg)
                    else:
                        _single_name, _single_data = _turn_results[0]
                        self.logger.info("\nSENDING FULL RESULT TO LLM via send_function_response")
                        _resume_response = self.llm_client.send_function_response(_single_name, _single_data, mem0_context=mem0_context_arg)
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

        # Skills tools
        elif tool_name == "skills.read_skill_file":
            skill_name = result.get("skill_name") or result.get("name", "unknown")
            return f"Loaded skill instructions: {skill_name}"

        elif tool_name == "skills.read_references":
            skill_name = result.get("skill_name", "unknown")
            file_path = result.get("file_path", "unknown")
            return f"Loaded reference: {skill_name}/{file_path}"

        elif tool_name == "skills.execute_script":
            exit_code = result.get("exit_code", result.get("returncode", "?"))
            stdout = result.get("stdout", result.get("output", ""))
            summary = stdout.strip()[:200] if stdout else "no output"
            return f"Script exit={exit_code}: {summary}"

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
