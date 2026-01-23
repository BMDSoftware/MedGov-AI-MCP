#!/usr/bin/env python3
import json
import requests
import subprocess
from typing import Dict, List, Optional, Any
from tool_registry import tool_registry


class ToolExecutor:
    """Handles MCP tool execution via stdio and HTTP protocols"""
    
    def __init__(self, available_tools: Dict[str, Any], callback=None):
        self.available_tools = available_tools
        self.callback = callback
    
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
        tool_registry.cleanup()