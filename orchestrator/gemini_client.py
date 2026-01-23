#!/usr/bin/env python3
import os
from typing import Dict, List, Any
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

load_dotenv()


class GeminiClient:
    """Handles Gemini AI client setup, tool schema conversion, and content generation"""
    
    def __init__(self, available_tools: Dict[str, Any]):
        self.genai_client = None
        self.available_tools = available_tools
        self.model_id = "gemini-2.5-flash"
        self.agent_config = None
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize Gemini with function calling capabilities using new google.genai Client"""
        # Initialize new genai client
        self.genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Convert MCP tools to Gemini function format
        gemini_tools_list = self._convert_tools_to_gemini_format()

        # Initialize the model with the converted tools
        self.agent_config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=gemini_tools_list)],
            system_instruction=self._get_system_prompt(),
            temperature=0.0 
        )
    
    def _convert_tools_to_gemini_format(self) -> List[types.FunctionDeclaration]:
        """Convert MCP tool schemas to Gemini FunctionDeclaration objects."""
        gemini_functions = []
        
        for tool_name, tool_info in self.available_tools.items():
            # Get the input schema from the MCP tool definition
            mcp_schema = tool_info.get("inputSchema", tool_info.get("schema", {}))
            
            # Recursively build the parameter schema
            gemini_parameters = self._build_gemini_schema(mcp_schema)
            
            # Create the Gemini FunctionDeclaration object
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
        
        # Handle properties for OBJECT types
        properties = None
        if gemini_type == "OBJECT" and "properties" in schema:
            properties = {
                k: self._build_gemini_schema(v) 
                for k, v in schema["properties"].items()
            }
        
        # Handle items for ARRAY types
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
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the AI agent"""
        tool_descriptions = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in self.available_tools.items()
        ])
        
        return f"""You are an autonomous AI agent for healthcare assistant.

Your tools:
{tool_descriptions}


Your role: Analyze goals, determine necessary steps, and if needed use tools to achieve outcomes.
Principles:
- Focus on OUTCOMES, not just actions
- Use tools that directly accomplish the goal
- When data is provided, use it in your tool calls (e.g., as 'payload' parameter)
- If a tool fails, analyze why and try a different approach
- Validate results match the goal before declaring success

You are autonomous - think critically about which tools achieve the goal most effectively."""
    
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
    
    def generate_content(self, content_parts: List, imageList: Any = None) -> Any:
        """Generate content using Gemini with optional image handling"""
        # Prepare content with actual images for Gemini
        if imageList:
            for temp_filepath, content in imageList:
                try:
                    # content is already bytes, use it directly
                    from io import BytesIO
                    img = Image.open(BytesIO(content))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    content_parts.append(img)
                    print(f"Added image to content from: {os.path.basename(temp_filepath)}")
                except Exception as e:
                    print(f"Error loading image from {temp_filepath}: {e}")
        
        return self.genai_client.models.generate_content(
            model=self.model_id,
            contents=content_parts,
            config=self.agent_config
        )