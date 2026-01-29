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

    def __init__(self, available_tools: Dict[str, Any]):
        self.genai_client = None
        self.chat_session = None  # Tracks the stateful conversation history
        self.available_tools = available_tools
        self.model_id = "gemini-2.0-flash" # Updated to current stable, use 2.5 if you have early access
        self.agent_config = None
        self.gemini_tools_list = []
        
        self._initialize_gemini()
        self.start_chat() # Initialize the chat session immediately

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
        tool_descriptions = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in self.available_tools.items()
        ])

        return f"""You are an autonomous AI agent for healthcare - a Multi-Agent Orchestrator for medical imaging analysis and report generation.

Your tools:
{tool_descriptions}

WORKFLOW FOR MEDICAL IMAGE ANALYSIS (FULL INFERENCE):
1. Call monai.analyze_image FIRST with the image path to get metadata
2. Call monai.list_models with modality AND body_part filters
3. If model exists but is not downloaded, call monai.download_model
4. Call monai.run_inference with the image path and model name
5. After inference, SUGGEST generating a report using radlex tools

WORKFLOW FOR REPORT GENERATION:
1. Use radlex.list_templates to find appropriate template
2. Use radlex.convert_findings_to_report_format
3. Use radlex.generate_report to create the final report

IMPORTANT RULES:
- 3D medical images (NIfTI, DICOM) work best with MONAI models
- After successful inference, report the detected structures and their volumes
- If tools change mid-session, adapt your strategy automatically.

You are autonomous - think critically about which tools achieve the goal most effectively."""
    
    def generate_content(self, prompt: str, imageList: Any = None) -> Any:
        """Send a message to the stateful chat session with optional image handling."""
        if isinstance(prompt, list):
            prompt = " ".join(map(str, prompt))

        # Start with the text part
        content_parts = [prompt]
        
        # Prepare content with actual images for Gemini
        if imageList:
            for temp_filepath, content in imageList:
                # Skip 3D medical formats - Gemini can't visualize these directly
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


