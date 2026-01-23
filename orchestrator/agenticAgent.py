#!/usr/bin/env python3
import json
import requests
import subprocess
from typing import Dict, List, Optional, Any
from google import generativeai as genai
import os
from dotenv import load_dotenv

from tool_registry import tool_registry

load_dotenv()


class AgenticAgent:
    """AI agent that decides which MCP tools to call based on context and data"""
    
    def __init__(self, callback=None):
        self.gemini_client = None
        self.available_tools = {}
        self.callback = callback  # Callback function for real-time event tracking
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize Gemini with function calling capabilities"""
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Discover available tools
        self.available_tools = tool_registry.discover_tools()
        
        # Convert MCP tools to Gemini function format
        gemini_functions = self._convert_tools_to_gemini_format()
        
        # Initialize Gemini with function calling
        self.gemini_client = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            tools=gemini_functions,
            system_instruction=self._get_system_prompt()
        )
    
    def _convert_tools_to_gemini_format(self) -> List[Dict]:
        """Convert MCP tool schemas to Gemini function calling format using actual schemas"""
        gemini_functions = []
        
        for tool_name, tool_info in self.available_tools.items():
            mcp_schema = tool_info.get("schema", {})
            
            # Build Gemini properties from actual MCP schema if available
            gemini_properties = {}
            required_fields = []
            
            if mcp_schema and mcp_schema.get("properties"):
                # Use actual MCP schema properties dynamically
                for prop_name, prop_def in mcp_schema.get("properties", {}).items():
                    mcp_type = prop_def.get("type", "string")
                    gemini_type = self._mcp_type_to_gemini(mcp_type)
                    
                    gemini_properties[prop_name] = {
                        "type": gemini_type,
                        "description": prop_def.get("description", f"{prop_name} parameter")
                    }
                
                # Extract required fields from schema
                required_fields = mcp_schema.get("required", [])
            else:
                # Fallback for tools without schema (shouldn't happen but defensive)
                gemini_properties = {
                    "type": {
                        "type": "STRING",
                        "description": "Resource type"
                    }
                }
            
            function_def = {
                "name": tool_name,
                "description": tool_info["description"],
                "parameters": {
                    "type": "OBJECT",
                    "properties": gemini_properties,
                    "required": required_fields
                }
            }
            
            gemini_functions.append(function_def)
        
        return gemini_functions
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the AI agent"""
        tool_descriptions = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in self.available_tools.items()
        ])
        
        return f"""You are an autonomous AI agent for healthcare data processing with access to FHIR tools.

Your tools:
{tool_descriptions}

Tool usage guide:
- search: Fetch/retrieve resources from FHIR server (use to GET data)
- create: Save NEW resources to FHIR server (use to POST data - requires 'type' and 'payload' with the data to save)
- read: Get a SPECIFIC resource by ID (use when you have an ID)
- update: Modify EXISTING resources (requires 'type', 'id', and 'payload')
- delete: Remove resources (requires 'type' and 'id')
- get_capabilities: Check server capabilities (rarely needed)

Your role: Analyze goals, determine which tools to use, and execute them to achieve the desired outcome.

Principles:
- Focus on OUTCOMES: "Save data" means use CREATE with the data as payload
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
                    image_context = f"\n\nIMAGES AVAILABLE:\nImage paths: {', '.join(imageList) if isinstance(imageList, list) else str(imageList)}"
                
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
                
                response = self.gemini_client.generate_content(prompt)
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
                            
                            result = self.execute_tool_decision(decision)
                            
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
        """Execute a tool decision using existing MCP infrastructure
        
        Args:
            decision: Tool decision with tool_name and arguments
            logs: If True, print detailed MCP/FHIR logs (default: False)
        """
        try:
            tool_name = decision["tool_name"]
            agent_arguments = decision["arguments"]
            
            if logs:
                print(f"Agent decided to call: {tool_name} with args: {agent_arguments}")
            
            # Convert protobuf to dict first (before callback and MCP conversion)
            clean_arguments = self._protobuf_to_dict(agent_arguments)
            
            # Notify callback of tool call start with clean arguments
            if self.callback:
                self.callback({
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "arguments": clean_arguments
                })
            
            # Get tool's information from registry
            tool_info = self.available_tools.get(tool_name, {})
            transport = tool_info.get("transport", "http")
            server_name = tool_info.get("server")
            original_name = tool_info.get("original_name", tool_name)
            
            if not server_name:
                raise Exception(f"No MCP server found for tool: {tool_name}")
            
            # Build MCP request
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": original_name,  # Use original tool name for MCP call
                    "arguments": clean_arguments
                },
                "id": 1
            }
            
            import time
            start_time = time.time()
            
            if transport == "stdio":
                result = self._execute_stdio_tool(server_name, mcp_request, logs)
            else:
                result = self._execute_http_tool(tool_info, mcp_request, logs)
                
            elapsed_time = time.time() - start_time
            
            if logs:
                print(f"🔧 Executed {tool_name} ({transport}) in {elapsed_time:.2f}s")
            
            # Notify callback of tool call completion
            if self.callback:
                self.callback({
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "success": bool(result),
                    "result": result
                })
            
            return result
            
        except Exception as e:
            if logs:
                print(f"\n{'='*80}")
                print(f"💥 EXCEPTION")
                print(f"{'='*80}")
                print(f"Tool execution failed: {e}")
                print(f"Exception type: {type(e).__name__}")
                import traceback
                print(f"Traceback:\n{traceback.format_exc()}")
                print(f"{'='*80}\n")
            
            # Notify callback of tool call failure
            if self.callback:
                self.callback({
                    "type": "tool_error",
                    "tool_name": tool_name,
                    "error": str(e)
                })
            
            return None
    
    
    def _execute_stdio_tool(self, server_name: str, mcp_request: Dict, logs: bool = False) -> Optional[Dict]:
        """Execute a tool call on a stdio MCP server"""
        from tool_registry import tool_registry
        
        # Get the process from tool registry
        if server_name not in tool_registry.server_processes:
            raise Exception(f"No active process found for server: {server_name}")
        
        process = tool_registry.server_processes[server_name]
        
        # Check if process is still running
        if process.poll() is not None:
            raise Exception(f"Server process {server_name} has terminated")
        
        if logs:
            print(f"\n{'='*80}")
            print(f"MCP STDIO REQUEST")
            print(f"{'='*80}")
            print(f"Server: {server_name}")
            print(f"Tool: {mcp_request['params']['name']}")
            print(f"Arguments: {json.dumps(mcp_request['params']['arguments'], indent=2)}")
            print(f"Full MCP Request: {json.dumps(mcp_request, indent=2)}")
            print(f"{'='*80}\n")
        
        # Send request to stdio process
        try:
            request_line = json.dumps(mcp_request) + "\n"
            process.stdin.write(request_line)
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            if not response_line:
                raise Exception("No response from stdio server")
            
            result_json = json.loads(response_line.strip())
            
            if logs:
                print(f"\n{'='*80}")
                print(f"MCP STDIO RESPONSE")
                print(f"{'='*80}")
                print(f"Response: {json.dumps(result_json, indent=2)}")
                print(f"{'='*80}\n")
            
            # Extract result from MCP response
            mcp_result = result_json.get("result", {})
            content = mcp_result.get("content", [])
            
            result = None
            if content and len(content) > 0:
                text = content[0].get("text", "")
                if text:
                    result = json.loads(text)
                    
                    if logs:
                        print(f"\n{'='*80}")
                        print(f"FHIR RESOURCE (STDIO)")
                        print(f"{'='*80}")
                        print(f"Resource Type: {result.get('resourceType', 'Unknown')}")
                        print(f"Resource ID: {result.get('id', 'N/A')}")
                        
                        if result.get('resourceType') == 'Bundle':
                            entry_count = len(result.get('entry', []))
                            print(f"Bundle Entries: {entry_count}")
                            if entry_count > 0:
                                first_entry = result['entry'][0].get('resource', {})
                                print(f"First Entry Type: {first_entry.get('resourceType', 'Unknown')}")
                        
                        print(f"Full Resource (first 500 chars):\n{json.dumps(result, indent=2)[:500]}...")
                        print(f"{'='*80}\n")
            
            # Check for errors in response
            if result_json.get("error"):
                error = result_json["error"]
                raise Exception(f"MCP error: {error.get('message', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            if logs:
                print(f"\n{'='*80}")
                print(f"STDIO ERROR")
                print(f"{'='*80}")
                print(f"Error: {e}")
                print(f"{'='*80}\n")
            raise e
    
    def _execute_http_tool(self, tool_info: Dict, mcp_request: Dict, logs: bool = False) -> Optional[Dict]:
        """Execute a tool call on an HTTP MCP server"""
        server_url = tool_info.get("server_url")
        if not server_url:
            raise Exception("No server URL found for HTTP tool")
        
        if logs:
            print(f"\n{'='*80}")
            print(f"MCP HTTP REQUEST")
            print(f"{'='*80}")
            print(f"Server URL: {server_url}/mcp/tools/call")
            print(f"Tool: {mcp_request['params']['name']}")
            print(f"Arguments: {json.dumps(mcp_request['params']['arguments'], indent=2)}")
            print(f"Full MCP Request: {json.dumps(mcp_request, indent=2)}")
            print(f"{'='*80}\n")
        
        # Call HTTP MCP server
        response = requests.post(
            f"{server_url}/mcp/tools/call",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            json=mcp_request
        )
        
        if logs:
            print(f"\n{'='*80}")
            print(f"MCP HTTP RESPONSE")
            print(f"{'='*80}")
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Body (first 1000 chars):\n{response.text[:1000]}...")
            print(f"{'='*80}\n")
        
        result = None
        if response.status_code == 200:
            result_json = response.json()
            mcp_result = result_json.get("result", {})
            content = mcp_result.get("content", [])
            
            if content and len(content) > 0:
                text = content[0].get("text", "")
                if text:
                    result = json.loads(text)
                    
                    if logs:
                        print(f"\n{'='*80}")
                        print(f"FHIR RESOURCE (HTTP)")
                        print(f"{'='*80}")
                        print(f"Resource Type: {result.get('resourceType', 'Unknown')}")
                        print(f"Resource ID: {result.get('id', 'N/A')}")
                        
                        if result.get('resourceType') == 'Bundle':
                            entry_count = len(result.get('entry', []))
                            print(f"Bundle Entries: {entry_count}")
                            if entry_count > 0:
                                first_entry = result['entry'][0].get('resource', {})
                                print(f"First Entry Type: {first_entry.get('resourceType', 'Unknown')}")
                        
                        print(f"Full Resource (first 500 chars):\n{json.dumps(result, indent=2)[:500]}...")
                        print(f"{'='*80}\n")
        else:
            # Log error details
            if logs:
                print(f"\n{'='*80}")
                print(f"HTTP ERROR")
                print(f"{'='*80}")
                print(f"Status Code: {response.status_code}")
                print(f"Error Response: {response.text}")
                print(f"{'='*80}\n")
            
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        return result

    def _extract_answer_from_results(self, agent_response: str, execution_history: List[Dict], final_result: Any) -> str:
        """Extract meaningful answer from agent response and execution results"""
        # Get the agent's text response (which should contain the answer)
        agent_text = agent_response.strip()
        
        # Look for the actual answer in the agent's response
        # The agent should provide the answer after declaring GOAL_ACHIEVED
        lines = agent_text.split('\n')
        answer_lines = []
        
        goal_achieved_found = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip the GOAL_ACHIEVED declaration itself
            if "GOAL_ACHIEVED" in line.upper() or "GOAL ACHIEVED" in line.upper():
                goal_achieved_found = True
                continue
                
            # Collect meaningful content after GOAL_ACHIEVED
            if goal_achieved_found and line:
                # Skip common technical phrases
                skip_phrases = [
                    "the last tool returned",
                    "mcp response",
                    "fhir response", 
                    "resource type"
                ]
                
                should_skip = any(phrase in line.lower() for phrase in skip_phrases)
                if not should_skip:
                    answer_lines.append(line)
        
        # If we found meaningful answer content, return it
        if answer_lines:
            return '\n'.join(answer_lines)
        
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
    
    def _protobuf_to_dict(self, obj: Any) -> Any:
        """Recursively convert protobuf MapComposite objects to Python dicts"""
        # Handle dict-like objects (including MapComposite)
        if hasattr(obj, 'items'):
            return {key: self._protobuf_to_dict(value) for key, value in obj.items()}
        # Handle list-like objects (including RepeatedComposite and regular lists)
        elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            return [self._protobuf_to_dict(item) for item in obj]
        # Primitive value
        else:
            return obj

    def cleanup(self):
        """Cleanup stdio server processes"""
        from tool_registry import tool_registry
        tool_registry.cleanup()

    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.cleanup()
        except (ImportError, AttributeError):
            # Python is shutting down, ignore cleanup errors
            pass


# Global agent instance
agent_decision = AgenticAgent()