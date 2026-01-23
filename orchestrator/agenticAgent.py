#!/usr/bin/env python3
import json
from typing import Dict, List, Optional, Any

from tool_registry import tool_registry
from gemini_client import GeminiClient
from tool_executor import ToolExecutor


class AgenticAgent:
    """AI agent that decides which MCP tools to call based on context and data"""
    
    def __init__(self, callback=None):
        self.available_tools = {}
        self.callback = callback  # Callback function for real-time event tracking
        self.gemini_client = None
        self.tool_executor = None
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize Gemini client and tool executor with discovered tools"""
        # Discover available tools
        self.available_tools = tool_registry.discover_tools()
        
        # Initialize components
        self.gemini_client = GeminiClient(self.available_tools)
        self.tool_executor = ToolExecutor(self.available_tools, self.callback)
    
    def execute_task(self, goal: str, data: Any = None, imageList: Any = None, max_iterations: int = 5) -> Optional[Dict]:
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
        
        while iterations < max_iterations:
            iterations += 1
            print(f"Iteration {iterations}/{max_iterations}")
            
            try:
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
                if imageList:
                    # Handle imageList as (temp_filepath, content) tuples
                    if isinstance(imageList, list) and imageList:
                        temp_files = [temp_filepath for temp_filepath, _ in imageList]
                        image_context = f"\n\nIMAGES AVAILABLE:\nImage file paths: {', '.join(temp_files)}"
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
                
                response = self.gemini_client.generate_content(content_parts, imageList)
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
                            
                            decision = {
                                "tool_name": tool_name,
                                "arguments": arguments
                            }
                            
                            result = self.tool_executor.execute_tool_decision(decision)
                            
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
                print(f"Error in iteration {iterations}: {e}")
                execution_history.append({
                    "tool": "error",
                    "success": False,
                    "error": str(e)
                })
        
        print(f"Failed to achieve goal after {max_iterations} iterations")
        return final_result
    
    def execute_tool_decision(self, decision: Dict, logs: bool = False) -> Optional[Dict]:
        """Execute a tool decision using existing MCP infrastructure - delegated to ToolExecutor"""
        return self.tool_executor.execute_tool_decision(decision, logs)

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

    def cleanup(self):
        """Cleanup stdio server processes"""
        if self.tool_executor:
            self.tool_executor.cleanup()

    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.cleanup()
        except (ImportError, AttributeError):
            # Python is shutting down, ignore cleanup errors
            pass


# Global agent instance
agent_decision = AgenticAgent()