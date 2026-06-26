#!/usr/bin/env python3
import os
from typing import Dict, List, Any
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv
from agent.prompts import AUTONOMOUS_PROMPT, BASE_SYSTEM_PROMPT

load_dotenv()


class GeminiClient:
    """Handles Gemini AI client setup, tool schema conversion, and stateful chat generation"""

    def __init__(self, available_tools: Dict[str, Any], skills, llm_mode: str = "stateful"):
        self.genai_client = None
        self.chat_session = None  # Tracks the stateful conversation history
        self.available_tools = available_tools
        self.model_id = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.agent_config = None
        self.gemini_tools_list = []
        self.custom_system_prompt = None  # Store custom system prompt
        self.mode_extension = ""  # Appended to system prompt in normal mode
        self.skills = skills  # Reference to skills manager for dynamic prompt generation
        self._llm_mode = llm_mode

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
        print("System prompt updated for patient conversation")

    def set_llm_mode(self, llm_mode: str):
        self._llm_mode = llm_mode

    @property
    def is_stateless_mode(self) -> bool:
        return self._llm_mode == "stateless"

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

    def start_chat(self, history: List = None):
        """Initializes a new stateful chat session."""
        self.chat_session = self.genai_client.chats.create(
            model=self.model_id,
            config=self.agent_config,
            history=history or []
        )
        print("New chat session started.")

    def serialize_history(self) -> list:
        """Serialize the current chat history to a JSON-serializable list."""
        if not self.chat_session:
            return []
        import json

        def _safe_dict(obj):
            try:
                return json.loads(json.dumps(obj))
            except Exception:
                try:
                    return json.loads(json.dumps(dict(obj), default=str))
                except Exception:
                    return {}

        result = []
        for content in self.chat_session.get_history():
            parts = []
            for part in content.parts:
                if part.text is not None:
                    parts.append({"type": "text", "text": part.text})
                elif part.function_call is not None:
                    fc = part.function_call
                    parts.append({"type": "function_call", "id": fc.id, "name": fc.name, "args": _safe_dict(fc.args)})
                elif part.function_response is not None:
                    fr = part.function_response
                    parts.append({"type": "function_response", "id": fr.id, "name": fr.name, "response": _safe_dict(fr.response)})
            if parts:
                result.append({"role": content.role, "parts": parts})
        return result

    def restore_history(self, history_data: list):
        """Restore a chat session from serialized history data."""
        if not history_data:
            self.start_chat()
            return
        history = []
        for item in history_data:
            parts = []
            for p in item.get("parts", []):
                if p["type"] == "text":
                    parts.append(types.Part(text=p["text"]))
                elif p["type"] == "function_call":
                    parts.append(types.Part(
                        function_call=types.FunctionCall(id=p.get("id"), name=p["name"], args=p["args"])
                    ))
                elif p["type"] == "function_response":
                    parts.append(types.Part(
                        function_response=types.FunctionResponse(id=p.get("id"), name=p["name"], response=p["response"])
                    ))
            if parts:
                history.append(types.Content(role=item["role"], parts=parts))
        self.start_chat(history=history)

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
        if self.is_stateless_mode:
            return AUTONOMOUS_PROMPT.format(available_skills=self.skills)
        return BASE_SYSTEM_PROMPT.format(available_skills=self.skills)
    
    def generate_content(self, prompt: str, fileList: Any = None) -> Any:
        """Send a message to the stateful chat session with optional image handling."""
        if isinstance(prompt, list):
            prompt = " ".join(map(str, prompt))

        # Start with the text part
        content_parts: List[Any] = [prompt]
        
        # Prepare content with actual images for Gemini
        image_paths = []
        if fileList:
            for temp_filepath, content in fileList:
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
                    image_paths.append(temp_filepath)
                    print(f"Added image to chat from: {os.path.basename(temp_filepath)}")
                except Exception as e:
                    print(f"Error loading image from {temp_filepath}: {e}")

        # Send the message using the CHAT SESSION, passing the most recent config
        # This automatically appends user input and model output to history.
        # Stateless: direct API call (no history); Stateful: chat session (history preserved)
        if self.is_stateless_mode:
            return self.genai_client.models.generate_content(
                model=self.model_id,
                contents=content_parts,
                config=self.agent_config,
            )
        return self.chat_session.send_message(
            message=content_parts,
            config=self.agent_config
        )

    def send_function_response(self, function_name: str, response_data: Any, images: list = None) -> Any:
        """Send a single function/tool result back to Gemini (stateful chat only)."""
        if self.is_stateless_mode:
            print(f"[stateless] send_function_response skipped for {function_name}")
            return None
        parts = [types.Part.from_function_response(
            name=function_name,
            response={"result": response_data}
        )]
        if images:
            print(f"Attaching {len(images)} image(s) to function response message for {function_name}")
            parts.extend(images)
        return self.chat_session.send_message(
            message=parts,
            config=self.agent_config
        )

    def send_multiple_function_responses(self, results: list, images: list = None) -> Any:
        """Send multiple function/tool results back to Gemini (stateful chat only)."""
        if self.is_stateless_mode:
            print(f"[stateless] send_multiple_function_responses skipped ({len(results)} results)")
            return None
        parts = [
            types.Part.from_function_response(
                name=name,
                response={"result": data}
            )
            for name, data in results
        ]
        if images:
            print(f"Attaching {len(images)} image(s) to function response message")
            parts.extend(images)
        return self.chat_session.send_message(
            message=parts,
            config=self.agent_config
        )
