#!/usr/bin/env python3
import os
import json
import asyncio
from typing import Dict
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

class ToolRegistry:
    def __init__(self):
        self.available_tools: Dict[str, Dict] = {}
        self.config_path = os.path.join(os.path.dirname(__file__), "mcp-config.json")
        self.stack = AsyncExitStack()
        self.sessions = {}


    def _load_mcp_config(self) -> Dict:
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Could not load MCP config: {e}")
            return {}


    async def discover_tools(self) -> Dict[str, Dict]:
        config = self._load_mcp_config()
        mcp_servers = config.get("mcpServers", {})

        if not mcp_servers:
            return {}

        print(f"Found {len(mcp_servers)} MCP servers: {list(mcp_servers.keys())}")

        for name, cfg in mcp_servers.items():
            print(f"--- Starting Server: {name} ---")
            transport = cfg.get("transport", "stdio")
            try:
                if transport == "stdio":
                    params = StdioServerParameters(
                        command=cfg["command"],
                        args=cfg.get("args", []),
                        env={**os.environ, **cfg.get("env", {})}
                    )
                    read, write = await self.stack.enter_async_context(stdio_client(params))
                    session = await self.stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    self.sessions[name] = (session, "stdio")
                elif transport == "http":
                    url = cfg.get("url", "http://localhost:8000/mcp")
                    read, write, _ = await self.stack.enter_async_context(streamable_http_client(url))
                    session = await self.stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    self.sessions[name] = (session, "http")

                tools = await session.list_tools()
                for tool in tools.tools:
                    prefixed_name = f"{name}.{tool.name}"
                    self.available_tools[prefixed_name] = {
                        "description": getattr(tool, "description", ""),
                        "schema": getattr(tool, "input_schema", {}),
                        "server": name,
                        "original_name": tool.name,
                        "transport": transport
                    }
                print(f"[{name}] Tools: {[t.name for t in tools.tools]}")

            except Exception as e:
                print(f"{name}: Failed to start: {e}")

        return self.available_tools


    async def execute_tool(self, tool_name: str, arguments: dict, logs: bool = False) -> dict:
        tool_info = self.available_tools.get(tool_name)
        if not tool_info:
            raise Exception(f"Tool not found: {tool_name}")
        
        server = tool_info["server"]
        session_tuple = self.sessions.get(server)
        if not session_tuple:
            raise Exception(f"No active session for server: {server}")
        
        session, transport = session_tuple
        clean_arguments = self._protobuf_to_dict(arguments)
        
        if logs:
            print(f"Executing '{tool_name}' on '{server}' (transport: {transport}) with args: {clean_arguments}")
            
        try:
            mcp_result = await session.call_tool(tool_info["original_name"], arguments=clean_arguments)
            
            combined_text = "".join([block.text for block in mcp_result.content if hasattr(block, 'text')])
            try:
                # If it's a JSON string, convert it to a real Python dictionary
                final_result = json.loads(combined_text)
                # Ensure the result is a dictionary (for .get() compatibility)
                if not isinstance(final_result, dict):
                    final_result = {"result": final_result}
            except (json.JSONDecodeError, TypeError):
                # If it's not JSON, return it as a dictionary with a 'text' key
                final_result = {"text": combined_text}

            # 4. Attach error status if the MCP server reported a failure
            if mcp_result.isError:
                final_result["is_error"] = True

            return final_result

        except Exception as e:
            print(f"Error executing tool '{tool_name}': {type(e).__name__}: {e}")
            return {"error": str(e), "is_error": True}


    def _protobuf_to_dict(self, obj):
        if isinstance(obj, dict):
            return {k: self._protobuf_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._protobuf_to_dict(v) for v in obj]
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        else:
            return obj


    async def close(self):
        """Cleanup stdio server processes"""
        await self.stack.aclose()


    async def reload_config_and_refresh(self) -> Dict[str, Dict]:
        """
        Reload MCP config and rediscover tools without closing sessions.
        Returns the refreshed available_tools dict.
        """
        # Do NOT close sessions here; just rediscover tools
        self.available_tools = {}
        # Optionally, you could re-initialize sessions if needed, but do not call self.close()
        await self.discover_tools()
        return self.available_tools




async def main():
    tool_registry = ToolRegistry()
    try:
        # Discover tools
        await tool_registry.discover_tools()

        # Execute a tool while the sessions are still alive
        if "monai.list_models" in tool_registry.available_tools:
            result = await tool_registry.execute_tool("monai.list_models", {}, logs=True)
            print(f"Result: {result}")
        else:
            print("monai.list_models not found.")
            
    finally:
        # Shut down everything cleanly
        await tool_registry.close()

if __name__ == "__main__":
    asyncio.run(main())