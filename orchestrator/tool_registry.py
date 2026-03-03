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
                config = json.load(f)
            return self._expand_vars(config)
        except Exception as e:
            print(f"Could not load MCP config: {e}")
            return {}

    @staticmethod
    def _expand_vars(obj):
        """Recursively expand ${VAR} / $VAR env vars in all string values."""
        if isinstance(obj, str):
            return os.path.expandvars(obj)
        if isinstance(obj, dict):
            return {k: ToolRegistry._expand_vars(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [ToolRegistry._expand_vars(v) for v in obj]
        return obj


    async def discover_tools(self) -> Dict[str, Dict]:
        config = self._load_mcp_config()
        mcp_servers = config.get("mcpServers", {})

        if not mcp_servers:
            return {}

        print(f"Found {len(mcp_servers)} MCP servers: {list(mcp_servers.keys())}")

        for name, cfg in mcp_servers.items():
            print(f"--- Starting Server: {name} ---")
            transport = cfg.get("transport", "stdio")
            # Use a per-server stack so that failed connections can be cleaned up
            # immediately without leaving dangling anyio task groups in self.stack
            # that would corrupt successful sessions (monai/utils).
            server_stack = AsyncExitStack()
            success = False
            try:
                if transport == "stdio":
                    params = StdioServerParameters(
                        command=cfg["command"],
                        args=cfg.get("args", []),
                        env={**os.environ, **cfg.get("env", {})}
                    )
                    read, write = await server_stack.enter_async_context(stdio_client(params))
                    session = await server_stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    self.sessions[name] = (session, "stdio")
                elif transport == "http":
                    url = cfg.get("url", "http://localhost:8000/mcp")
                    read, write, _ = await server_stack.enter_async_context(streamable_http_client(url))
                    session = await server_stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    self.sessions[name] = (session, "http")

                tools = await session.list_tools()
                for tool in tools.tools:
                    prefixed_name = f"{name}.{tool.name}"
                    self.available_tools[prefixed_name] = {
                        "description": getattr(tool, "description", ""),
                        "schema": getattr(tool, "inputSchema", {}),
                        "server": name,
                        "original_name": tool.name,
                        "transport": transport
                    }
                print(f"[{name}] Tools: {[t.name for t in tools.tools]}")
                success = True

            except asyncio.CancelledError:
                # anyio cancel scopes call task.cancel() when a child task fails
                # (e.g. subprocess exits). This increments task.cancelling() even
                # though it's fhir's OWN internal cancellation, not an external one.
                # Uncancel so the cleanup awaits in `finally` don't immediately
                # re-raise, then treat it as a normal connection failure.
                task = asyncio.current_task()
                if task is not None and task.cancelling() > 0:
                    task.uncancel()
                print(f"[{name}] Not available - skipping (CancelledError)")
            except Exception as e:
                print(f"[{name}] Not available - skipping ({type(e).__name__})")
            finally:
                if success:
                    # Hand off cleanup to the main stack via callback
                    self.stack.push_async_callback(server_stack.aclose)
                else:
                    # Close failed server's resources immediately.
                    # At this point the failed server's anyio task group scope is
                    # at the top of the scope stack, so exiting it is safe and
                    # won't affect successful sessions below it.
                    try:
                        await server_stack.aclose()
                    except BaseException as cleanup_err:
                        print(f"[{name}] Cleanup warning: {type(cleanup_err).__name__}")
                    if name in self.sessions:
                        del self.sessions[name]

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

            # Attach error status if the MCP server reported a failure
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