#!/usr/bin/env python3
from hmac import new
import json
import os
from typing import Dict, List, Any
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv
from logger import Logger

load_dotenv()


class GeminiClient:
    """Handles Gemini AI client setup, tool schema conversion, and stateless generation.
    
    Each task gets a fresh conversation_history (an ephemeral list of
    types.Content objects needed by the stateless generate_content API for
    multi-turn tool use).  Cross-task memory is provided by mem0, not by
    Gemini chat sessions.
    """

    def __init__(self, available_tools: Dict[str, Any], skills):
        self.genai_client = None
        self.conversation_history: List = []  # Ephemeral per-task turn history
        self.available_tools = available_tools
        self.model_id = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.agent_config = None
        self.gemini_tools_list = []
        self.custom_system_prompt = None  # Store custom system prompt
        self.mode_extension = ""  # Appended to system prompt in normal mode
        self.skills = skills  # Reference to skills manager for dynamic prompt generation
        self._call_count = 0  # Track iteration number

        self._initialize_gemini()

    def set_mode_extension(self, ext: str):
        """Set an extra block appended to the system prompt, then rebuild config."""
        self.mode_extension = ext
        self.update_tools(self.available_tools)

    def update_system_prompt(self, system_prompt: str):
        """Update the system prompt and reset conversation history."""
        self.custom_system_prompt = system_prompt
        # Use _get_system_prompt() so any active mode_extension is preserved
        self.agent_config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=self.gemini_tools_list)],
            system_instruction=self._get_system_prompt(),
            temperature=0.0
        )
        self.reset_conversation()
        print("System prompt updated for patient conversation")

    def set_model(self, model_id: str):
        """Switch to a different model, preserving the current chat history."""
        if model_id == self.model_id:
            return
        history = list(self.chat_session.get_history()) if self.chat_session else []
        self.model_id = model_id
        self.start_chat(history=history)
        print(f"Switched to model: {model_id}")

    def _initialize_gemini(self):
        """Initialize Gemini using new google.genai Client"""
        self.genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.update_tools(self.available_tools)

    def reset_conversation(self):
        """Clear the ephemeral per-task conversation history."""
        self.conversation_history = []
        print("Conversation history reset.")

    def update_tools(self, available_tools: Dict[str, Any]):
        """Update Gemini's available tools dynamically.
        Will apply to the VERY NEXT message sent in the chat."""
        self.available_tools = available_tools
        self.gemini_tools_list = self._convert_tools_to_gemini_format()
        
        self.agent_config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=self.gemini_tools_list)],
            system_instruction=self._get_system_prompt(),
            temperature=0.0
        )
        print(f"Tools updated. Current active tools: {list(self.available_tools.keys())}")
    
    def _convert_tools_to_gemini_format(self) -> List[types.FunctionDeclaration]:
        """Convert MCP tool schemas to Gemini FunctionDeclaration objects."""
        gemini_functions = []
        
        for tool_name, tool_info in self.available_tools.items():
            mcp_schema = tool_info.get("inputSchema", tool_info.get("schema", {}))
            gemini_parameters = self._build_gemini_schema(mcp_schema)
            

            function_def = types.FunctionDeclaration(
                name=tool_name,
                description=tool_info.get("description", "No description provided"),
                parameters=gemini_parameters
            )
            gemini_functions.append(function_def)
        
        return gemini_functions

    def _build_gemini_schema(self, schema: Dict[str, Any]) -> types.Schema:
        """Recursively converts standard JSON schema to Gemini types.Schema."""
        mcp_type = schema.get("type", "object")
        gemini_type = self._mcp_type_to_gemini(mcp_type)
        
        properties = None
        if gemini_type == "OBJECT" and "properties" in schema:
            properties = {
                k: self._build_gemini_schema(v) 
                for k, v in schema["properties"].items()
            }
        
        items = None
        if gemini_type == "ARRAY" and "items" in schema:
            items = self._build_gemini_schema(schema["items"])

        return types.Schema(
            type=gemini_type,
            description=schema.get("description"),
            properties=properties,
            required=schema.get("required", []),
            items=items
        )
    
    def _mcp_type_to_gemini(self, mcp_type: str) -> str:
        """Convert MCP JSON Schema type to Gemini type"""
        type_mapping = {
            "string": "STRING",
            "integer": "INTEGER",
            "number": "NUMBER",
            "boolean": "BOOLEAN",
            "object": "OBJECT",
            "array": "ARRAY"
        }
        return type_mapping.get(mcp_type.lower(), "STRING")

    def _get_system_prompt(self) -> str:
        """Get system prompt for the AI agent"""
        base = self.custom_system_prompt if self.custom_system_prompt else None
        if base is None:
            base = self._base_system_prompt()
        if self.mode_extension:
            return base + "\n\n" + self.mode_extension
        return base

    def _base_system_prompt(self) -> str:
        """Default system prompt when no custom prompt is set"""
        skills_section = ""
        if self.skills and self.skills != "No skills available":
            skills_section = f"""

---

# AVAILABLE SKILLS (DIRECTORY)
{self.skills}

Only use skills listed above and tools available in the system. Do not attempt to use, guess, or simulate any skill not present in this directory, same for tools.

---

# SKILL USAGE PROTOCOL

You do not have full skill instructions pre-loaded. You must follow this exact workflow for every clinical task, silently and without narrating your steps to the user:

**Step 1 — IDENTIFY**
Determine which skill from the directory is required. If no skill matches the request, respond:
> "I do not have the specific clinical skill required for this task."
Do not proceed further.

**Step 2 — READ**
Call `read_skill_file(skill_name)` to load the detailed instructions for that skill. Do not execute any domain tools before completing this step.

**Step 3 — EXPLORE (if needed)**
If the SKILL.md references additional schemas or technical files, call `read_references(skill_name, file_path)` to retrieve them before proceeding.

**Step 4 — EXECUTE**
Follow the instructions returned by the skill file precisely. Use the domain tools specified (e.g., `monai.*`, `fhir.*`). If the skill includes executable scripts, call `execute_script(skill_name, script_name, parameters)`.

**Step 5 — INTERPRET & RESPOND**
Treat all tool outputs as raw clinical observations. Apply professional interpretation before presenting findings to the user. For reports, be thorough and specific: include all findings, relevant values, flags, and clinical context. Never present raw tool output without interpretation.

---

# SKILL OPERATIONAL RULES

- **One skill at a time.** If a request spans multiple skills, handle each sequentially and silently, completing one before starting the next.
- **No hallucinations.** Never guess, simulate, or infer skill outputs. If a tool returns unexpected or empty data, state this to the user rather than filling gaps with assumptions.
- **Re-read on new tasks.** Do not assume skill instructions are cached between turns. Re-read the SKILL.md for each new task unless the same skill was used in the immediately preceding step of the same task.
- **Skill independence.** Skill outputs do not override your clinical reasoning — you are responsible for interpreting results in the context of the patient's data.
- **Missing patient context.** If required patient data is absent or incomplete, ask the user to provide it before calling any tools.
- **Capability questions** ("What can you do?"): Describe the available skills from the directory above. Do not call any tools to answer this.
- **Clinical action requests**: Execute the full 5-step protocol silently. Only speak when you have a final result, a clarifying question, or an error to surface.
- **Ambiguous requests**: Ask one clarifying question before selecting a skill.

---

# SKILL ERROR HANDLING

- If `read_skill_file()` fails or returns empty: retry once silently, then surface a brief error message to the user if it fails again.
- If a domain tool returns an error code: surface the status to the user concisely without technical jargon.
- If results appear clinically inconsistent or out of expected range: flag this explicitly in your response before providing interpretation."""
        return skills_section
        return f"""You are a healthcare AI assistant. You help medical professionals by analyzing medical images, parsing DICOM files, generating radiology reports, and retrieving patient data.

You have access to MCP tools that you can call directly. The tools are already registered and available to you - use them when the user requests an action.

BACKGROUND TASK RULES:
- Any operation that takes more than a few seconds MUST be queued via run_inference (which auto-queues) rather than a direct blocking call.
- This includes: MONAI inference, report generation, bulk analysis of multiple files.
- After queuing a task, respond to the user immediately — do NOT wait for the task to finish.
- The user will receive a notification in the UI when the task is done.

CONVERSATION RULES:
1. Be conversational. If the user greets you, greet them back. If they ask a question you can answer from context, answer it directly without calling any tool.
2. You have memory of previous interactions in this session. If the user asks about something that was already retrieved (e.g. modality, body part), answer from what you already know - do not re-call the tool.
3. Respond concisely and directly. Do not over-explain your reasoning.

TOOL USAGE RULES:
1. Only call a tool when the user requests an action that requires it AND the required parameters are available.
2. NEVER invent file paths. If a tool needs a file path, use the one from "IMAGES AVAILABLE" in the context. If none is available, ask the user to upload or provide one.
3. For DICOM files (.dcm): parse the metadata first to extract modality and body part before selecting models or running inference.
4. MONAI models require 3D volumes (.nii, .nii.gz). If the image is a single 2D slice, inform the user.
5. Do not repeat a tool call that already failed. Explain the error and ask how to proceed.
6. After a tool returns results, summarize them clearly for the user.
7. MULTI-FILE RULE: When multiple paths are listed in "IMAGES AVAILABLE" and the user asks to analyze or run inference, process ALL of them. Call the appropriate tool for each path one by one. Do not stop after the first.
8. DIRECTORY RULE: A path marked as [DICOM SERIES DIR] is a directory of DICOM slices forming a single 3D volume. Pass the directory path directly to analyze_image or run_inference — MONAI handles it natively. Do NOT iterate individual files inside the directory."""
    
    # ------------------------------------------------------------------
    # Stateless generation helpers
    # ------------------------------------------------------------------

    def _serialize_part(self, part) -> str:
        """Convert a single Content Part to a readable string for logging."""
        if hasattr(part, 'text') and part.text:
            return f"[TEXT] {part.text[:2000]}{'…' if len(part.text) > 2000 else ''}"
        if hasattr(part, 'function_call') and part.function_call:
            fc = part.function_call
            args = dict(fc.args) if fc.args else {}
            return f"[FUNCTION_CALL] {fc.name}({json.dumps(args, default=str)})"
        if hasattr(part, 'function_response') and part.function_response:
            fr = part.function_response
            resp_str = json.dumps(dict(fr.response) if fr.response else {}, default=str)
            if len(resp_str) > 2000:
                resp_str = resp_str[:2000] + '…'
            return f"[FUNCTION_RESPONSE] {fr.name} -> {resp_str}"
        if hasattr(part, 'inline_data') and part.inline_data:
            return f"[IMAGE] mime={getattr(part.inline_data, 'mime_type', 'unknown')}"
        return f"[OTHER] {type(part).__name__}"

    def _first_with_mem0(self, content: types.Content, mem0_context: str) -> types.Content:
        """Return a copy of content with mem0_context appended as a text part.

        Bug 3a fix: the context injected here is always the current AgentState + goal
        check prompt, not historical mem0 memory. Label it as CURRENT TASK STATE to
        avoid confusing the LLM into thinking it's reading past session history.
        """
        # Detect whether this looks like actual mem0 session memory or current state
        if mem0_context.strip().startswith("{") and "completed_steps" in mem0_context:
            label = "CURRENT TASK STATE"
        elif mem0_context.strip().startswith("SESSION MEMORY"):
            label = "SESSION MEMORY (from previous interactions)"
        else:
            label = "CURRENT TASK STATE"
        mem0_part = types.Part.from_text(
            text=f"\n\n---\n{label}:\n{mem0_context}\n---"
        )
        return types.Content(role=content.role, parts=list(content.parts or []) + [mem0_part])

    def _build_send_contents(self, new_content: types.Content, mem0_context: str = "") -> List:
        """Build the minimal list of Content objects to send to Gemini.

        Every call sends:
          • First user message  : goal + mem0 context injected dynamically
          • Last two tool call/response pairs (4 messages): provides the model
            with enough recent context to avoid repeating already-executed steps
          • new_content         : the function_response or next user prompt

        Old completed call/response pairs beyond the last two are dropped.
        mem0 carries cross-turn memory so the model doesn't need to re-read
        prior tool payloads.
        """
        # new_content was just appended to conversation_history by _call_model
        history = self.conversation_history

        if len(history) <= 3:
            # Not enough turns to trim anything; send everything
            if mem0_context and history:
                return [self._first_with_mem0(history[0], mem0_context)] + list(history[1:])
            return list(history)

        # [0] first user message (goal) — with mem0 context injected on every call
        first = self._first_with_mem0(history[0], mem0_context) if mem0_context else history[0]
        # [-2:] last two tool call/response pairs (call + result each)
        recent = history[-2:]
        return [first] + recent

    def _call_model(self, new_content: types.Content, mem0_context: str= "") -> Any:
        """Append *new_content* to history, then call generate_content with
        goal + mem0 context + last tool result (if any).
        Full history is kept locally for logging; mem0 provides cross-turn memory."""
        self._call_count += 1

        self.conversation_history.append(new_content)
        send_contents = self._build_send_contents(new_content, mem0_context)

        print(f"\n{'='*80}")
        print("Whats sending to Gemini:")
        print(send_contents)
        print(f"{'='*80}\n")
        response = self.genai_client.models.generate_content(
            model=self.model_id,
            contents=send_contents,
            config=self.agent_config,
        )

        # Record the model's reply in full local history for the next iteration's trim.
        # Skip empty responses — they poison the trim window: when history[-2] is an
        # empty model turn, the next call sends [goal] + [empty] + [prompt] and the
        # model loses all context about what tools already ran.
        if response.candidates and response.candidates[0].content:
            content = response.candidates[0].content
            parts = content.parts or []
            has_meaningful_content = any(
                (hasattr(p, "text") and p.text and p.text.strip())
                or hasattr(p, "function_call")
                for p in parts
            )
            if has_meaningful_content:
                self.conversation_history.append(content)
            

        return response

    def generate_content(self, prompt: str, imageList: Any = None, mem0_context: str = "") -> Any:
        """Build a user Content from text + optional images, then call the model."""
        if isinstance(prompt, list):
            prompt = " ".join(map(str, prompt))

        # Start with the text part
        parts: list = [types.Part.from_text(text=prompt)]

        # Prepare content with actual images for Gemini
        if imageList:
            for temp_filepath, content in imageList:
                # Skip directories (DICOM series) and 3D medical formats
                if os.path.isdir(temp_filepath):
                    print(f"Skipping DICOM series directory (not sendable to Gemini): {os.path.basename(temp_filepath)}")
                    continue
                ext = temp_filepath.lower()
                if ext.endswith(('.nii', '.nii.gz', '.dcm', '.mha', '.mhd', '.nrrd')):
                    print(f"Skipping 3D medical file (not sendable to Gemini): {os.path.basename(temp_filepath)}")
                    continue

                try:
                    from io import BytesIO
                    img = Image.open(BytesIO(content))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    parts.append(img)
                    print(f"Added image to prompt from: {os.path.basename(temp_filepath)}")
                except Exception as e:
                    print(f"Error loading image from {temp_filepath}: {e}")

        user_content = types.Content(role="user", parts=parts)
        return self._call_model(user_content, mem0_context=mem0_context)

    def send_function_response(self, function_name: str, response_data: Any, mem0_context: str= "") -> Any:
        """Send a single function/tool result back to Gemini."""
        part = types.Part.from_function_response(
            name=function_name,
            response={"result": response_data},
        )
        user_content = types.Content(role="user", parts=[part])
        return self._call_model(user_content, mem0_context=mem0_context)

    def send_multiple_function_responses(self, results: list, mem0_context: str = "") -> Any:
        """Send multiple function/tool results back to Gemini in a single message.
        Required when Gemini issued multiple function calls in the same turn.
        results: list of (function_name, response_data) tuples, one per call."""
        parts = [
            types.Part.from_function_response(
                name=name,
                response={"result": data},
            )
            for name, data in results
        ]
        user_content = types.Content(role="user", parts=parts)
        return self._call_model(user_content, mem0_context=mem0_context)
