#!/usr/bin/env python3
from ast import Set
import os
import json
from re import S
from typing import Dict, List, Optional, Any

from tool_registry import ToolRegistry

# LLM Backend selection: "ollama" (local) or "gemini" (API)
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")

# Workflow state machine for medical imaging analysis
# This enforces the correct sequence of tool calls
WORKFLOW_STEPS = [
    {"name": "analyze", "tool": "monai.analyze_image", "required": True},
    {"name": "list", "tool": "monai.list_models", "required": True},
    {"name": "download", "tool": "monai.download_model", "required": False},  # Only if not downloaded
    {"name": "inference", "tool": "monai.run_inference", "required": True},
]


class AgenticAgent:
    """AI agent that decides which MCP tools to call based on context and data"""

    def __init__(self, callback=None):
        self.tool_registry = ToolRegistry()
        self.available_tools = {}
        self.agent_tools: Set[str] = set()
        self.callback = callback  # Callback function for real-time event tracking
        self.llm_client = None
        self.workflow_state = {}  # Track workflow progress
        # Use async init pattern for tool discovery
        # You must call await self._initialize_components() after instantiation

    async def _initialize_components(self):
        """Initialize LLM client and tool registry with discovered tools"""
        self.available_tools = await self.tool_registry.discover_tools()
        self.agent_tools = set(self.available_tools.keys())
        enabled_tools = self.get_enabled_agent_tools()
        if LLM_BACKEND.lower() == "ollama":
            print("Using Ollama (local) for orchestration")
            from ollama_client import OllamaClient
            self.llm_client = OllamaClient(enabled_tools)
        else:
            print("Using Gemini (API) for orchestration")
            from gemini_client import GeminiClient
            self.llm_client = GeminiClient(enabled_tools)

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

    def _get_workflow_state(self, execution_history: List[Dict]) -> Dict:
        """Analyze execution history to determine workflow state"""
        state = {
            "analyze_done": False,
            "list_done": False,
            "download_done": False,
            "inference_done": False,
            "image_path": None,
            "model_name": None,
            "model_downloaded": False,
            "inference_result": None,
        }

        for event in execution_history:
            if not event.get("success"):
                continue

            tool = event.get("tool", "")
            result = event.get("result", {})

            if tool == "monai.analyze_image":
                state["analyze_done"] = True
                # Extract image path from result if available
                if isinstance(result, dict):
                    state["image_path"] = result.get("path") or result.get("file_path")
                    print(f"  [Workflow] analyze_image done, path={state['image_path']}")

            elif tool == "monai.list_models":
                state["list_done"] = True
                # Check if any model is downloaded
                if isinstance(result, dict):
                    models = result.get("models", [])
                    print(f"  [Workflow] list_models found {len(models)} models")
                    for model in models:
                        if model.get("downloaded"):
                            state["model_downloaded"] = True
                            state["model_name"] = model.get("name")
                            print(f"  [Workflow] Found downloaded model: {state['model_name']}")
                            break
                    # If no downloaded model, pick the first one
                    if not state["model_name"] and models:
                        state["model_name"] = models[0].get("name")
                        print(f"  [Workflow] Selected model to download: {state['model_name']}")

            elif tool == "monai.download_model":
                state["download_done"] = True
                state["model_downloaded"] = True
                # Extract model name from result
                if isinstance(result, dict) and result.get("model_name"):
                    state["model_name"] = result.get("model_name")
                print(f"  [Workflow] download_model done, model={state['model_name']}")

            elif tool == "monai.run_inference":
                state["inference_done"] = True
                state["inference_result"] = result
                print(f"  [Workflow] run_inference done")

        return state

    def _get_next_workflow_step(self, state: Dict, image_path: str) -> Optional[Dict]:
        """Determine the next tool to call based on workflow state"""
        if not state["analyze_done"]:
            print("  [Next step] analyze_image")
            return {
                "tool_name": "monai.analyze_image",
                "arguments": {"path": image_path}
            }

        if not state["list_done"]:
            print("  [Next step] list_models")
            return {
                "tool_name": "monai.list_models",
                "arguments": {}
            }

        # If we have a model but it's not downloaded yet, download it
        if state["model_name"] and not state["model_downloaded"]:
            print(f"  [Next step] download_model ({state['model_name']})")
            return {
                "tool_name": "monai.download_model",
                "arguments": {"model_name": state["model_name"]}
            }

        # Run inference if we have a downloaded model
        if not state["inference_done"] and state["model_name"] and state["model_downloaded"]:
            print(f"  [Next step] run_inference with model {state['model_name']}")
            return {
                "tool_name": "monai.run_inference",
                "arguments": {
                    "image_path": state["image_path"] or image_path,
                    "model_name": state["model_name"]
                }
            }

        # Workflow complete
        print("  [Next step] None - workflow complete")
        return None

    async def execute_task(self, goal: str, data: Any = None, imageList: Any = None, max_iterations: int = 8) -> Optional[Dict]:
        """
        Truly autonomous task execution - agent reasons about tools and executes

        Args:
            goal: Natural language description of what to accomplish
            data: Optional data context (e.g., patient data to save)
            imageList: Optional list of images for processing
            max_iterations: Maximum number of tool executions allowed

        Returns:
            Final result if successful, None if goal not achieved
        """
        print(f"Starting autonomous task: {goal}")

        execution_history = []
        iterations = 0
        final_result = None

        # Extract image path for workflow
        image_path = None
        if imageList and isinstance(imageList, list) and imageList:
            image_path = imageList[0][0]  # First image's temp file path
            print(f"Image path for workflow: {image_path}")

        # Use guided workflow for local LLMs (Ollama)
        use_guided_workflow = LLM_BACKEND.lower() == "ollama"

        while iterations < max_iterations:
            iterations += 1
            print(f"Iteration {iterations}/{max_iterations}")
            try:
                if use_guided_workflow and image_path:
                    workflow_state = self._get_workflow_state(execution_history)
                    print(f"Workflow state: analyze={workflow_state['analyze_done']}, list={workflow_state['list_done']}, download={workflow_state['download_done']}, inference={workflow_state['inference_done']}")

                    # Check if workflow is complete
                    if workflow_state["inference_done"]:
                        print("Workflow complete! Inference has been run.")
                        tools_used = [event['tool'] for event in execution_history if event['success']]

                        # Format the inference result
                        inference_result = workflow_state.get("inference_result", {})
                        answer = "GOAL_ACHIEVED\n\n**Medical Image Analysis Complete**\n"

                        if isinstance(inference_result, dict):
                            # Add model info
                            if inference_result.get("model_used"):
                                answer += f"\n**Model:** {inference_result['model_used']}\n"
                            if inference_result.get("model_type"):
                                answer += f"**Analysis Type:** {inference_result['model_type']}\n"
                            if inference_result.get("device_used"):
                                answer += f"**Device:** {inference_result['device_used']}\n"

                            # Add detection/segmentation results
                            results = inference_result.get("results", {})
                            if results.get("detected_structures"):
                                answer += "\n**Detected Structures:**\n"
                                for struct in results["detected_structures"]:
                                    name = struct.get("name", "Unknown")
                                    vol_pct = struct.get("volume_percentage", "N/A")
                                    voxels = struct.get("voxel_count", "N/A")
                                    answer += f"  - {name}: {vol_pct}% of volume ({voxels} voxels)\n"

                            if results.get("total_foreground_voxels"):
                                answer += f"\n**Total foreground:** {results['total_foreground_voxels']} voxels\n"

                            # Add status
                            if inference_result.get("status") == "success":
                                answer += "\nInference completed successfully.\n"

                        return {
                            "type": "agent_response",
                            "answer": answer,
                            "tools_used": tools_used,
                            "execution_history": execution_history,
                            "inference_result": inference_result,
                            "success": True
                        }

                    # Get next step from workflow state machine
                    next_step = self._get_next_workflow_step(workflow_state, image_path)

                    if next_step:
                        print(f"Guided workflow: Next step is {next_step['tool_name']}")
                        print(f"  Arguments: {next_step['arguments']}")
                        # FIX: Await the async execute_tool call
                        result = await self.tool_registry.execute_tool(next_step["tool_name"], next_step["arguments"], logs=True)
                        if result:
                            if isinstance(result, dict) and result.get("error"):
                                error_msg = result.get("error")
                                print(f"Tool returned error: {error_msg}")
                                execution_history.append({
                                    "tool": next_step["tool_name"],
                                    "success": False,
                                    "error": error_msg,
                                    "result": result
                                })
                            else:
                                execution_history.append({
                                    "tool": next_step["tool_name"],
                                    "success": True,
                                    "result": result
                                })
                        else:
                            execution_history.append({
                                "tool": next_step["tool_name"],
                                "success": False,
                                "error": "No result returned",
                                "result": None
                            })
                        continue  # Move to next iteration

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
                
                image_context = ""
                images_for_llm = None  # Only pass 2D images to LLM (if supported)

                if imageList:
                    # Handle imageList as (temp_filepath, content) tuples
                    if isinstance(imageList, list) and imageList:
                        temp_files = [temp_filepath for temp_filepath, _ in imageList]
                        image_context = f"\n\nIMAGES AVAILABLE:\nImage file paths: {', '.join(temp_files)}"

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

                if not execution_history:
                    # First iteration - let agent decide what to do
                    prompt = f"""GOAL: {goal}{data_context}{image_context}

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
                        
                        if hasattr(part, 'function_call') and part.function_call:
                            has_function_call = True
                            tool_name = part.function_call.name
                            arguments = dict(part.function_call.args)
                            
                            # Check if agent is repeating a failed tool
                            if execution_history:
                                last_event = execution_history[-1]
                                if last_event.get('tool') == tool_name and not last_event.get('success'):
                                    print(f"Agent tried to repeat failed tool '{tool_name}' - skipping and prompting for alternative")
                                    execution_history.append({
                                        "tool": tool_name,
                                        "success": False,
                                        "error": f"Repetition prevented: Tool '{tool_name}' already failed. Try a different tool."
                                    })
                                    continue
                            
                            # Execute the tool
                            print(f"Executing: {tool_name}")
                            
                            
                            result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)
                            
                            # Record execution with result details
                            if result:
                                # Create human-readable summary for agent
                                result_type = result.get("resourceType", "unknown")
                                result_summary = f"{result_type}"
                                if result_type == "Bundle":
                                    entry_count = len(result.get("entry", []))
                                    result_summary += f" with {entry_count} entries"
                                elif result_type == "Patient":
                                    result_id = result.get("id", "no-id")
                                    result_summary += f" (id: {result_id})"
                                
                                execution_history.append({
                                    "tool": tool_name,
                                    "success": True,
                                    "result_type": result_type,
                                    "result_summary": result_summary,
                                    "result": result  # Store actual result
                                })
                                
                                final_result = result
                                print(f"Tool succeeded: {result_summary}")
                            else:
                                execution_history.append({
                                    "tool": tool_name,
                                    "success": False,
                                    "error": "Execution returned no result"
                                })
                                print(f"Tool execution failed")
                
                # If agent didn't call a tool or declare success, it's confused
                if not has_function_call and not (has_text and "GOAL" in response.text.upper()):
                    print(f"Agent didn't call a tool or declare success")
                    execution_history.append({
                        "tool": "none",
                        "success": False,
                        "error": "Agent did not select a tool or declare success"
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
    
    def _extract_answer_from_results(self, agent_response: str, execution_history: List[Dict], final_result: Any) -> str:
        """Extract meaningful answer from agent response and execution results"""
        # Get the agent's text response (which should contain the answer)
        agent_text = agent_response.strip()
        
        # If the response contains GOAL_ACHIEVED, return the entire response
        if "GOAL_ACHIEVED" in agent_text.upper() or "GOAL ACHIEVED" in agent_text.upper():
            return agent_text
        
        # Fallback: try to extract meaningful information from the last successful result
        if execution_history:
            for event in reversed(execution_history):
                if event['success'] and event.get('result'):
                    result = event['result']
                    
                    # For any FHIR resource, return basic info
                    if isinstance(result, dict) and result.get('resourceType'):
                        resource_type = result.get('resourceType')
                        resource_id = result.get('id', 'unknown')
                        return f"{resource_type} resource successfully processed with ID: {resource_id}"
        
        # Last fallback: return a generic success message
        return "Goal achieved successfully"


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