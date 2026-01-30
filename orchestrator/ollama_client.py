#!/usr/bin/env python3
"""
Ollama Client for local LLM orchestration
Uses Ollama Chat API with native tool/function calling support
"""

import os
import json
import requests
from typing import Dict, List, Any, Optional


class OllamaClient:
    """Handles Ollama local LLM for orchestration with native tool calling"""

    def __init__(self, available_tools: Dict[str, Any], model: str = None):
        self.available_tools = available_tools
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.chat_history = []  # Maintain conversation history
        self.tools = self._convert_tools_to_ollama_format()
        print(f"Ollama client initialized with model: {self.model}")
        print(f"Tools available: {list(self.available_tools.keys())}")

    def update_tools(self, available_tools: Dict[str, Any]):
        """Update Ollama's available tools dynamically."""
        self.available_tools = available_tools
        self.tools = self._convert_tools_to_ollama_format()
        print(f"Tools updated. Current active tools: {list(self.available_tools.keys())}")

    def _convert_tools_to_ollama_format(self) -> List[Dict]:
        """Convert MCP tool schemas to Ollama tool format (OpenAI-compatible)."""
        ollama_tools = []

        for tool_name, tool_info in self.available_tools.items():
            # Get the input schema from the MCP tool definition
            mcp_schema = tool_info.get("inputSchema", tool_info.get("schema", {}))

            tool_def = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_info.get("description", "No description provided"),
                    "parameters": mcp_schema
                }
            }
            ollama_tools.append(tool_def)

        return ollama_tools

    def _get_system_prompt(self) -> str:
        """Get system prompt for the AI agent"""
        tool_descriptions = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in self.available_tools.items()
        ])

        return f"""You are a healthcare AI assistant with access to tools.

YOUR AVAILABLE TOOLS:
{tool_descriptions}

CRITICAL RULES:

1. NEVER INVENT FILE PATHS. If a tool needs a file path and none is provided in the context:
   - Check if "IMAGES AVAILABLE:" is in the context - if yes, use that path
   - If no images in context, respond: "I need an image file to analyze. Please upload one or provide the file path."

2. WHEN TO RESPOND WITH TEXT (no tool call):
   - Greetings → respond with text
   - "What tools do you have?" → list the tools above
   - Missing required parameters → ask for them

3. WHEN TO CALL A TOOL:
   - User requests an action AND all required parameters are available
   - Say: "I'll use [tool] because [reason]. The file is at [path from context]."
   - Call the tool with the ACTUAL path from context
   - Summarize result, then say "GOAL_ACHIEVED"

4. DO NOT repeat failed tools. If a tool fails, explain the error and ask how to proceed.

TOOL NAMES: Always use full prefix (monai.list_models, fhir.search, radlex.generate_report)"""

    def start_chat(self, history: List = None):
        """Start a new chat session or restore history."""
        self.chat_history = history or []
        print("New Ollama chat session started.")

    def generate_content(self, prompt: str, imageList: Any = None) -> Any:
        """Send a message to Ollama with tool calling support."""
        if isinstance(prompt, list):
            prompt = " ".join(str(p) for p in prompt)

        # Add image context if available
        if imageList:
            image_paths = [fp for fp, _ in imageList]
            prompt += f"\n\nImage files available at: {', '.join(image_paths)}"

        # Add user message to history
        user_message = {"role": "user", "content": prompt}

        # Build messages array with system prompt
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            *self.chat_history,
            user_message
        ]

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": self.tools if self.tools else None,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 2048
                    }
                },
                timeout=180
            )
            response.raise_for_status()
            result = response.json()

            # Extract the assistant's response
            assistant_message = result.get("message", {})
            content = assistant_message.get("content", "")
            tool_calls = assistant_message.get("tool_calls", [])

            # Log for debugging
            print(f"Ollama response content: {content[:200] if content else 'No content'}...")
            if tool_calls:
                print(f"Ollama tool calls: {[tc.get('function', {}).get('name') for tc in tool_calls]}")

            # Add to chat history
            self.chat_history.append(user_message)
            self.chat_history.append(assistant_message)

            # Convert to Gemini-compatible format
            return OllamaResponse(content, tool_calls)

        except requests.exceptions.Timeout:
            print("Ollama request timed out")
            raise
        except Exception as e:
            print(f"Ollama error: {e}")
            raise


class OllamaResponse:
    """Wrapper to make Ollama response compatible with Gemini response format"""

    def __init__(self, content: str, tool_calls: List[Dict] = None):
        self.raw_text = content
        self.text = content
        self.candidates = [OllamaCandidate(content, tool_calls)]


class OllamaCandidate:
    """Wrapper for Ollama candidate"""

    def __init__(self, content: str, tool_calls: List[Dict] = None):
        self.content = OllamaContent(content, tool_calls)


class OllamaContent:
    """Wrapper for Ollama content with parts"""

    def __init__(self, content: str, tool_calls: List[Dict] = None):
        self.parts = self._build_parts(content, tool_calls)

    def _build_parts(self, content: str, tool_calls: List[Dict] = None) -> List:
        """Build parts from content and tool calls"""
        parts = []

        # Add tool calls as function_call parts
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")

                # Parse arguments - could be string or dict
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                parts.append(OllamaFunctionCall(name=name, args=args))

        # FALLBACK: If no tool_calls but content has JSON, try to parse it
        if not tool_calls and content:
            extracted = self._extract_tool_call_from_text(content)
            if extracted:
                parts.append(OllamaFunctionCall(name=extracted["name"], args=extracted["args"]))
                # Remove the JSON from content for cleaner text
                content = ""

        # Add text content if present
        if content:
            parts.append(OllamaTextPart(content))

        # If no parts, add empty text
        if not parts:
            parts.append(OllamaTextPart(""))

        return parts

    def _extract_tool_call_from_text(self, text: str) -> Optional[Dict]:
        """Try to extract a tool call from text content (fallback for models that don't use native tool calling)"""
        import re

        # Look for JSON object with "name" and "parameters" keys
        # Match patterns like: {"name": "tool.name", "parameters": {...}}
        json_pattern = r'\{[^{}]*"name"\s*:\s*"([^"]+)"[^{}]*"parameters"\s*:\s*(\{[^{}]*\})[^{}]*\}'
        match = re.search(json_pattern, text)

        if match:
            try:
                name = match.group(1)
                params_str = match.group(2)
                params = json.loads(params_str)
                print(f"Extracted tool call from text: {name} with params: {params}")
                return {"name": name, "args": params}
            except (json.JSONDecodeError, IndexError):
                pass

        # Try simpler approach - find any JSON object in the text
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                if "name" in data:
                    params = data.get("parameters", data.get("arguments", {}))
                    print(f"Extracted tool call from JSON: {data['name']} with params: {params}")
                    return {"name": data["name"], "args": params}
        except json.JSONDecodeError:
            pass

        return None


class OllamaTextPart:
    """Text part wrapper"""
    def __init__(self, text: str):
        self.text = text
        self.function_call = None


class OllamaFunctionCall:
    """Function call wrapper compatible with Gemini format"""
    def __init__(self, name: str, args: Dict):
        self.name = name
        self.args = args
        self.text = None

    @property
    def function_call(self):
        return self
