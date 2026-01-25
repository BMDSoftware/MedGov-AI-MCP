#!/usr/bin/env python3
from json import tool
import os
import json
import subprocess
import sys
from typing import Dict, List


class ToolRegistry:
    """Dynamic tool registry that discovers available MCP tools"""
    
    def __init__(self):
        self.available_tools: Dict[str, Dict] = {}
        self.config_path = os.path.join(os.path.dirname(__file__), "mcp-config.json")
        self.server_processes: Dict[str, subprocess.Popen] = {}
    

    def reload_config_and_refresh(self) -> Dict[str, Dict]:
        """Reload config file and refresh available tools/servers"""
        print("Reloading MCP config and refreshing tools...")
        return self.discover_tools()
    
    def _load_mcp_config(self) -> Dict:
        """Load MCP configuration from config file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Could not load MCP config: {e}")
            return {}
    
    def discover_tools(self) -> Dict[str, Dict]:
        """Discover available tools from all MCP servers in config"""
        try:
            # Load config to get all servers
            config = self._load_mcp_config()
            self.available_tools = {}
            mcp_servers = config.get("mcpServers", {})
            
            if not mcp_servers:
                print(f"No MCP servers found in config")
                print(f"Configuration required - no tools available")
                self.available_tools = {}
                return self.available_tools
            
            print(f"Found {len(mcp_servers)} MCP servers: {list(mcp_servers.keys())}")
            
            # Discover tools from each server
            for server_name, server_config in mcp_servers.items():
                print(f"Discovering tools from '{server_name}' server...")
                transport = server_config.get("transport", "http")
                
                if transport == "stdio":
                    self._discover_from_stdio_server(server_name, server_config)
                else:
                    self._discover_from_http_server(server_name, server_config)
            
        except Exception as e:
            print(f"Tool discovery failed: {e}")
            print(f"MCP servers unreachable - no tools available")
            self.available_tools = {}
            
        print(f"Discovered {len(self.available_tools)} tools: {list(self.available_tools.keys())}")
        return self.available_tools
    
    def _discover_from_stdio_server(self, server_name: str, server_config: Dict):
        """Discover tools from a stdio-based MCP server"""
        command = server_config.get("command")
        args = server_config.get("args", [])
        cwd = server_config.get("cwd")
        env_vars = server_config.get("env", {})
        
        if not command:
            print(f"{server_name}: No command specified")
            return
        
        try:
            # Start the MCP server process
            full_command = [command] + args

            
            process = subprocess.Popen(
                full_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=cwd,
                env=env_vars if env_vars else None
            )
            
            # Store the process for later cleanup
            self.server_processes[server_name] = process
            
            # Step 1: Send initialize request (MCP protocol requirement)
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "orchestrator",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            }
            
            process.stdin.write(json.dumps(init_request) + "\n")
            process.stdin.flush()
            
            # Read initialize response
            init_response = process.stdout.readline()
            if not init_response:
                raise Exception("No response from server during initialization")
            
            # Step 2: Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            process.stdin.write(json.dumps(initialized_notification) + "\n")
            process.stdin.flush()
            
            # Step 3: Send tools/list request
            request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 2
            }
            
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            if not response_line:
                raise Exception("No response from server")
            
            result = json.loads(response_line)
            tools_list = result.get("result", {}).get("tools", [])
            
            # Process discovered tools from this server
            for tool in tools_list:
                tool_name = tool.get("name", "")
                # Prefix tool name with server name
                prefixed_tool_name = f"{server_name}.{tool_name}"
                self.available_tools[prefixed_tool_name] = {
                    "description": tool.get("description", ""),
                    "schema": tool.get("inputSchema", {}),
                    "server": server_name,
                    "original_name": tool_name,
                    "transport": "stdio"
                }
            
            print(f"{server_name}: Discovered {len(tools_list)} tools via stdio")
            
        except Exception as e:
            print(f"{server_name}: Failed to discover tools - {e}")
            if server_name in self.server_processes:
                self.server_processes[server_name].terminate()
                del self.server_processes[server_name]
    
    def _discover_from_http_server(self, server_name: str, server_config: Dict):
        """Discover tools from an HTTP-based MCP server"""
        mcp_server_url = server_config.get("url", "http://localhost:8000")
        
        import requests
        
        response = requests.post(
            f"{mcp_server_url}/mcp/tools/list",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            json={
                "jsonrpc": "2.0",
                "method": "tools/list", 
                "id": 1
            },
            timeout=5
        )
        
        print(f"{server_name}: {response.status_code} from {mcp_server_url}/tools/list")
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code} from {server_name}")
            
        result = response.json()
        tools_list = result.get("result", {}).get("tools", [])
        
        # Process discovered tools from this server
        for tool in tools_list:
            tool_name = tool.get("name", "")
            # Prefix tool name with server name
            prefixed_tool_name = f"{server_name}.{tool_name}"
            self.available_tools[prefixed_tool_name] = {
                "description": tool.get("description", ""),
                "schema": tool.get("inputSchema", {}),
                "server": server_name,
                "original_name": tool_name,
                "server_url": mcp_server_url,
                "transport": "http"
            }
        
        print(f"{server_name}: Discovered {len(tools_list)} tools via HTTP")
    
    def cleanup(self):
        """Cleanup stdio server processes"""
        for server_name, process in list(self.server_processes.items()):
            try:
                if process.poll() is None:  # Only if still running
                    process.terminate()
                    process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self.server_processes.clear()
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.cleanup()
        except (ImportError, AttributeError):
            # Python is shutting down, ignore cleanup errors
            pass
    

            

# Create global tool registry instance
tool_registry = ToolRegistry()
tool_registry.discover_tools()