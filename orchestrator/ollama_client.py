#!/usr/bin/env python3
"""
Ollama Client for local LLM orchestration
Uses Ollama API to run local models like deepseek-r1
"""

import os
import json
import requests
from typing import Dict, List, Any, Optional


class OllamaClient:
    """Handles Ollama local LLM for orchestration decisions"""

    def __init__(self, available_tools: Dict[str, Any], model: str = None):
        self.available_tools = available_tools
        self.model = model or os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.system_prompt = self._get_system_prompt()
        print(f"Ollama client initialized with model: {self.model}")

    
    def update_tools(self, available_tools: Dict[str, Any]):
        """Update Ollama's available tools and sync config."""
        self.available_tools = available_tools
        self.system_prompt = self._get_system_prompt()

    def _get_system_prompt(self) -> str:
        """Get system prompt for the AI agent"""
        tool_descriptions = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in self.available_tools.items()
        ])

        # Build tool schemas for function calling
        tool_schemas = []
        for name, info in self.available_tools.items():
            schema = {
                "name": name,
                "description": info.get("description", ""),
                "parameters": info.get("inputSchema", info.get("schema", {}))
            }
            tool_schemas.append(schema)

        return f"""You are a medical imaging AI agent. You execute tools to analyze medical images.

AVAILABLE TOOLS:
{tool_descriptions}

STRICT WORKFLOW - Follow these steps IN ORDER:

STEP 1: Analyze the image
{{"tool": "monai.analyze_image", "arguments": {{"path": "<image_path>"}}}}

STEP 2: List available models (filter by modality and body_part from step 1)
{{"tool": "monai.list_models", "arguments": {{"modality": "CT", "body_part": "abdomen"}}}}

STEP 3: Download the model (if "downloaded": false)
{{"tool": "monai.download_model", "arguments": {{"model_name": "spleen_ct_segmentation"}}}}

STEP 4: Run inference
{{"tool": "monai.run_inference", "arguments": {{"image_path": "<image_path>", "model_name": "spleen_ct_segmentation"}}}}

STEP 5: When inference is complete, declare success:
{{"status": "GOAL_ACHIEVED", "result": "<summary of findings>"}}

CRITICAL RULES:
- Respond with ONLY valid JSON, no other text
- Do NOT repeat the same tool call twice
- Do NOT skip steps - you MUST download and run inference
- After list_models, you MUST call download_model next
- After download_model, you MUST call run_inference next
- Only declare GOAL_ACHIEVED after run_inference returns results"""

    def generate_content(self, content_parts: List, imageList: Any = None) -> Any:
        """Generate content using Ollama"""
        # Build the prompt from content parts
        prompt = ""
        for part in content_parts:
            if isinstance(part, str):
                prompt += part

        # Add image context (paths only, Ollama can't see images)
        if imageList:
            image_paths = [fp for fp, _ in imageList]
            prompt += f"\n\nImage files available at: {', '.join(image_paths)}"

        # Call Ollama API
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1024
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            llm_response = result.get("response", "")

            # Log the raw response for debugging
            print(f"Ollama raw response: {llm_response[:500]}...")

            # Parse the response and convert to Gemini-like format
            return OllamaResponse(llm_response)

        except Exception as e:
            print(f"Ollama error: {e}")
            raise


class OllamaResponse:
    """Wrapper to make Ollama response compatible with Gemini response format"""

    def __init__(self, text: str):
        self.raw_text = text
        self.candidates = [OllamaCandidate(text)]
        self.text = text


class OllamaCandidate:
    """Wrapper for Ollama candidate"""

    def __init__(self, text: str):
        self.content = OllamaContent(text)


class OllamaContent:
    """Wrapper for Ollama content with parts"""

    def __init__(self, text: str):
        self.parts = self._parse_response(text)

    def _parse_response(self, text: str) -> List:
        """Parse Ollama response to extract tool calls or text"""
        parts = []

        # Try to find JSON in the response
        try:
            # Look for JSON block in markdown code fence
            if "```json" in text:
                json_start = text.find("```json") + 7
                json_end = text.find("```", json_start)
                json_str = text[json_start:json_end].strip()
            elif "```" in text:
                json_start = text.find("```") + 3
                json_end = text.find("```", json_start)
                json_str = text[json_start:json_end].strip()
            elif "{" in text and "}" in text:
                # Try to find raw JSON
                json_start = text.find("{")
                json_end = text.rfind("}") + 1
                json_str = text[json_start:json_end]
            else:
                json_str = None

            if json_str:
                data = json.loads(json_str)

                # Check if it's a tool call
                if "tool" in data:
                    parts.append(OllamaFunctionCall(
                        name=data["tool"],
                        args=data.get("arguments", {})
                    ))
                    return parts

                # Check if goal achieved
                if data.get("status") == "GOAL_ACHIEVED":
                    parts.append(OllamaTextPart(f"GOAL_ACHIEVED\n{data.get('result', '')}"))
                    return parts

        except json.JSONDecodeError:
            pass

        # Fallback: return as text
        parts.append(OllamaTextPart(text))
        return parts


class OllamaTextPart:
    """Text part wrapper"""
    def __init__(self, text: str):
        self.text = text
        self.function_call = None


class OllamaFunctionCall:
    """Function call wrapper"""
    def __init__(self, name: str, args: Dict):
        self.name = name
        self.args = args
        self.text = None

    @property
    def function_call(self):
        return self
