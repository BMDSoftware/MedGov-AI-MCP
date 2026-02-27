#!/usr/bin/env python3
import os
from typing import Dict, List, Any
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

load_dotenv()


class GeminiClient:
    """Handles Gemini AI client setup, tool schema conversion, and stateful chat generation"""

    def __init__(self, available_tools: Dict[str, Any], skills):
        self.genai_client = None
        self.chat_session = None  # Tracks the stateful conversation history
        self.available_tools = available_tools
        self.model_id = "gemini-2.0-flash"
        self.agent_config = None
        self.gemini_tools_list = []
        self.custom_system_prompt = None  # Store custom system prompt
        self.mode_extension = ""  # Appended to system prompt in normal mode
        self.skills = skills  # Reference to skills manager for dynamic prompt generation

        self._initialize_gemini()
        self.start_chat() # Initialize the chat session immediately

    def set_mode_extension(self, ext: str):
        """Set an extra block appended to the system prompt, then restart the chat."""
        self.mode_extension = ext
        self.update_tools(self.available_tools)

    def update_system_prompt(self, system_prompt: str):
        """Update the system prompt and restart chat session"""
        self.custom_system_prompt = system_prompt
        # Use _get_system_prompt() so any active mode_extension is preserved
        self.agent_config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=self.gemini_tools_list)],
            system_instruction=self._get_system_prompt(),
            temperature=0.0
        )
        # Restart chat session with new config
        self.start_chat()
        print(f"System prompt updated for patient conversation")

    def _initialize_gemini(self):
        """Initialize Gemini using new google.genai Client"""
        self.genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.update_tools(self.available_tools)

    def start_chat(self, history: List = None):
        """Initializes a new stateful chat session."""
        self.chat_session = self.genai_client.chats.create(
            model=self.model_id,
            config=self.agent_config,
            history=history or []
        )
        print("New chat session started.")

    def update_tools(self, available_tools: Dict[str, Any]):
        """Update Gemini's available tools dynamically.
        Will apply to the VERY NEXT message sent in the chat."""
        self.available_tools = available_tools
        self.gemini_tools_list = self._convert_tools_to_gemini_format()
        
        self.agent_config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=self.gemini_tools_list)],
            system_instruction=self._get_system_prompt(),
            temperature=0.0
            # Note: If you pass actual python functions instead of just declarations, 
            # you can add `automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)` here.
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
        # # Old skills-based prompt:
        # tool_descriptions = "\n".join([
        #     f"- {name}: {info['description']}"
        #     for name, info in self.available_tools.items()
        # ])
        # # Skills-based prompt (from friend's branch - commented out, using conversational prompt instead):
        #return f"""
        #  # ROLE
        #  You are a specialized Healthcare AI Assistant. Your operations are strictly bound to the medical context of the current patient.
        #  
        #  # AVAILABLE SKILLS (DIRECTORY)
        #  {self.skills}
        #  Only use the skills listed in the directory above. Each skill has specific instructions and rules that you must follow precisely. Do not attempt to use any skill that is not in the directory.
        #  # SKILL USAGE PROTOCOL (PROGRESSIVE DISCLOSURE)
        #  You do not have all instructions loaded into your memory at once. You must follow this tiered workflow:
        #  1. **DISCOVERY (Current State):** You can see the "Available Skills" list above. If a user asks "What can you do?", explain these skills based on their descriptions. Do NOT call a tool just to list them.
        #  2. **READ SKILL:** When a task requires a specific skill, call `skills.read_skill_file(skill_name)` to get the detailed instructions and rules (SKILL.md) for that domain.
        #  3. **EXPLORE REFERENCES:** If you need deeper technical details or schemas mentioned in the SKILL.md, then use `skills.read_references(skill_name, file_path)` to read specific reference files.
        #  4. **EXECUTE:** After reading the skill instructions, proceed to use the specific domain tools (e.g., `monai.*`, `fhir.*`). If the skill has executable scripts, use `skills.execute_script(skill_name, script_name, parameters)`.
        #  # OPERATIONAL RULES
        #  - **One at a Time:** Work with only one skill at a time.
        #  - **No Hallucinations:** If you do not have a skill that matches the user's request, state: "I do not have the specific clinical skill required for this task." Do not attempt to guess or simulate skill outputs.
        #  - **Independence:** Skills are external resources. Treat their outputs as clinical observations that require your professional interpretation.
        #  # INTERACTION GUIDELINES
        #  - **If the user asks for information/capabilities:** Read from the "Available Skills" list above and describe them.
        #  - **If the user requests a clinical action (e.g., "Analyze the labs"):**
        #      1. Identify the correct skill from the directory.
        #      2. Call `skills.read_skill_file(skill_name)`.
        #      3. Follow the instructions returned by that tool to complete the request.
        #  # EMERGENCY & SAFETY
        #  If the patient's data appears critical or the tools return error codes, prioritize clear communication of the status over performing complex analysis."""

        return """You are a healthcare AI assistant. You help medical professionals by analyzing medical images, parsing DICOM files, generating radiology reports, and retrieving patient data.

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
    
    def generate_content(self, prompt: str, imageList: Any = None) -> Any:
        """Send a message to the stateful chat session with optional image handling."""
        if isinstance(prompt, list):
            prompt = " ".join(map(str, prompt))

        # Start with the text part
        content_parts = [prompt]
        
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
                    content_parts.append(img)
                    print(f"Added image to chat from: {os.path.basename(temp_filepath)}")
                except Exception as e:
                    print(f"Error loading image from {temp_filepath}: {e}")

        # Send the message using the CHAT SESSION, passing the most recent config
        # This automatically appends user input and model output to history.
        return self.chat_session.send_message(
            message=content_parts,
            config=self.agent_config
        )
    
    def send_function_response(self, function_name: str, response_data: Any) -> Any:
        """Send a single function/tool result back to Gemini."""
        function_response = types.Part.from_function_response(
            name=function_name,
            response={"result": response_data}
        )
        return self.chat_session.send_message(
            message=[function_response],
            config=self.agent_config
        )

    def send_multiple_function_responses(self, results: list) -> Any:
        """Send multiple function/tool results back to Gemini in a single message.
        Required when Gemini issued multiple function calls in the same turn.
        results: list of (function_name, response_data) tuples, one per call."""
        parts = [
            types.Part.from_function_response(
                name=name,
                response={"result": data}
            )
            for name, data in results
        ]
        return self.chat_session.send_message(
            message=parts,
            config=self.agent_config
        )
