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
        self.gemini_tools_list = []
        self._initialize_gemini()

    def _initialize_gemini(self):
        """Initialize Gemini with function calling capabilities using new google.genai Client"""
        self.genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.update_tools(self.available_tools)

    def update_tools(self, available_tools: Dict[str, Any]):
        """Update Gemini's available tools and sync config."""
        self.available_tools = available_tools
        self.gemini_tools_list = self._convert_tools_to_gemini_format()
        self.agent_config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=self.gemini_tools_list)],
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

        return f"""You are an autonomous AI agent for healthcare - a Multi-Agent Orchestrator for medical imaging analysis and report generation.

Your tools:
{tool_descriptions}

WORKFLOW FOR MEDICAL IMAGE ANALYSIS (FULL INFERENCE):
1. Call monai.analyze_image FIRST with the image path to get metadata and check if image is ready for inference
2. Call monai.list_models with modality AND body_part filters to find suitable models
3. If a suitable model exists but is not downloaded, call monai.download_model to download it
4. Call monai.run_inference with the image path and model name to run REAL AI inference
5. The inference results will show detected structures, segmentation results, or detection findings
6. After inference, SUGGEST generating a report using radlex tools

WORKFLOW FOR REPORT GENERATION:
1. Use radlex.list_templates to find appropriate template based on modality and body part
2. Use radlex.convert_findings_to_report_format to convert AI inference results to report format
3. Use radlex.generate_report to create the final report
4. Use radlex.get_impression_suggestions to help write the impression section

IMPORTANT RULES:
- ALWAYS filter models by BOTH modality AND body_part (e.g., CT + abdomen)
- Check if model is "downloaded: true" before running inference
- If model is not downloaded, download it first with download_model
- For JPEG/PNG images from the user, trust the modality they specified (CT, MRI, etc.)
- 3D medical images (NIfTI, DICOM) work best with MONAI models
- 2D images (JPEG, PNG) will be converted to pseudo-3D but results may be less accurate
- After successful inference, report the detected structures and their volumes

EXAMPLE FULL WORKFLOW:
1. analyze_image("/path/to/ct.nii.gz") -> shows CT, abdomen, recommends spleen_ct_segmentation
2. list_models(modality="CT", body_part="abdomen") -> shows available models, check if downloaded
3. download_model("spleen_ct_segmentation") -> downloads if needed
4. run_inference("/path/to/ct.nii.gz", "spleen_ct_segmentation") -> returns segmentation results with detected organs

DATA TYPES YOU CAN HANDLE:
- Medical images (DICOM, NIfTI, PNG, JPEG) -> use monai.* tools for real AI inference
- Report generation -> use radlex.* tools
- Patient data (FHIR) -> use fhir.* tools (if available)

Principles:
- RUN ACTUAL INFERENCE using run_inference - don't just list models
- Focus on OUTCOMES - provide real AI analysis results
- If a tool fails, analyze why and try a different approach
- Validate results match the goal before declaring success
- ALWAYS offer next steps after completing an action

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
        # Only send 2D images (JPEG, PNG) - skip 3D medical formats (NIfTI, DICOM)
        if imageList:
            for temp_filepath, content in imageList:
                # Skip 3D medical formats - Gemini can't visualize these
                ext = temp_filepath.lower()
                if ext.endswith(('.nii', '.nii.gz', '.dcm', '.mha', '.mhd', '.nrrd')):
                    print(f"Skipping 3D medical file (not sendable to Gemini): {os.path.basename(temp_filepath)}")
                    continue

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

        print("Tools available to Gemini:", list(self.available_tools.keys()))
        
        return self.genai_client.models.generate_content(
            model=self.model_id,
            contents=content_parts,
            config=self.agent_config
        )