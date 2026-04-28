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
                print(f"[{name}] Not available - skipping ({type(e).__name__}: {e})")
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
            
        async def _call(sess):
            mcp_result = await sess.call_tool(tool_info["original_name"], arguments=clean_arguments)
            combined_text = "".join([block.text for block in mcp_result.content if hasattr(block, 'text')])
            try:
                final_result = json.loads(combined_text)
                if not isinstance(final_result, dict):
                    final_result = {"result": final_result}
            except (json.JSONDecodeError, TypeError):
                final_result = {"text": combined_text}
            if mcp_result.isError:
                final_result["is_error"] = True
            return final_result

        try:
            return await _call(session)
        except Exception as e:
            err_str = str(e)
            print(f"Error executing tool '{tool_name}': {type(e).__name__}: {err_str}")
            # If the MCP subprocess died (Connection closed / EOF), try to restart
            # the session once so subsequent calls work again.
            if any(kw in err_str.lower() for kw in ("connection closed", "eof", "broken pipe", "closed")):
                print(f"[tool_registry] Dead session for '{server}', restarting...")
                try:
                    new_session = await self._restart_server(server)
                    if new_session:
                        return await _call(new_session)
                except Exception as restart_err:
                    print(f"[tool_registry] Restart failed for '{server}': {restart_err}")
            return {"error": err_str, "is_error": True}


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


    async def _restart_server(self, name: str):
        """Restart a dead MCP server session using its existing config entry. Returns new session."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            cfg = config.get("mcpServers", {}).get(name)
            if not cfg:
                print(f"[tool_registry] No config found for '{name}', cannot restart.")
                return None
        except Exception as e:
            print(f"[tool_registry] Could not read config for restart: {e}")
            return None

        # Remove the stale session entry
        self.sessions.pop(name, None)

        cfg = self._expand_vars(cfg)
        transport = cfg.get("transport", "stdio")
        server_stack = AsyncExitStack()
        try:
            if transport == "stdio":
                params = StdioServerParameters(
                    command=cfg["command"],
                    args=cfg.get("args", []),
                    env={**os.environ, **cfg.get("env", {})}
                )
                read, write = await server_stack.enter_async_context(stdio_client(params))
            elif transport == "http":
                url = cfg.get("url", "")
                read, write, _ = await server_stack.enter_async_context(streamable_http_client(url))
            else:
                return None

            session = await server_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[name] = (session, transport)
            self.stack.push_async_callback(server_stack.aclose)

            # Refresh tools for this server
            tools = await session.list_tools()
            old_keys = [k for k in self.available_tools if k.startswith(f"{name}.")]
            for k in old_keys:
                del self.available_tools[k]
            for tool in tools.tools:
                prefixed_name = f"{name}.{tool.name}"
                self.available_tools[prefixed_name] = {
                    "description": getattr(tool, "description", ""),
                    "schema": getattr(tool, "inputSchema", {}),
                    "server": name,
                    "original_name": tool.name,
                    "transport": transport,
                }
            print(f"[tool_registry] Restarted '{name}' successfully.")
            return session
        except Exception as e:
            print(f"[tool_registry] Failed to restart '{name}': {e}")
            try:
                await server_stack.aclose()
            except BaseException:
                pass
            return None

    async def refresh_server_tools(self, name: str) -> Dict[str, Dict]:
        """Re-query tools from an already-connected server."""
        if name not in self.sessions:
            raise Exception(f"Server '{name}' is not connected.")
        session, transport = self.sessions[name]
        # Remove old tools for this server
        old_keys = [k for k in self.available_tools if k.startswith(f"{name}.")]
        for k in old_keys:
            del self.available_tools[k]
        # Re-list tools
        tools = await session.list_tools()
        new_tools = {}
        for tool in tools.tools:
            prefixed_name = f"{name}.{tool.name}"
            tool_info = {
                "description": getattr(tool, "description", ""),
                "schema": getattr(tool, "inputSchema", {}),
                "server": name,
                "original_name": tool.name,
                "transport": transport
            }
            self.available_tools[prefixed_name] = tool_info
            new_tools[prefixed_name] = tool_info
        print(f"[{name}] Refreshed tools: {list(new_tools.keys())}")
        return new_tools

    async def add_server(self, name: str, cfg: dict) -> Dict[str, Dict]:
        """Connect a new MCP server live and register its tools. Returns new tools dict."""
        if name in self.sessions:
            raise Exception(f"Server '{name}' already connected.")
        cfg = self._expand_vars(cfg)
        transport = cfg.get("transport", "stdio")
        server_stack = AsyncExitStack()
        success = False
        new_tools = {}
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
                url = cfg.get("url", "")
                read, write, _ = await server_stack.enter_async_context(streamable_http_client(url))
                session = await server_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                self.sessions[name] = (session, "http")
            else:
                raise Exception(f"Unknown transport: {transport}")

            tools = await session.list_tools()
            for tool in tools.tools:
                prefixed_name = f"{name}.{tool.name}"
                tool_info = {
                    "description": getattr(tool, "description", ""),
                    "schema": getattr(tool, "inputSchema", {}),
                    "server": name,
                    "original_name": tool.name,
                    "transport": transport
                }
                self.available_tools[prefixed_name] = tool_info
                new_tools[prefixed_name] = tool_info
            print(f"[{name}] Connected. Tools: {list(new_tools.keys())}")
            success = True

            # Persist to mcp-config.json
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                config.setdefault("mcpServers", {})[name] = cfg
                with open(self.config_path, 'w') as f:
                    json.dump(config, f, indent=2)
            except Exception as e:
                print(f"Warning: could not persist new server to config: {e}")

        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                task.uncancel()
            raise Exception(f"Connection cancelled for server '{name}'")
        except Exception:
            raise
        finally:
            if success:
                self.stack.push_async_callback(server_stack.aclose)
            else:
                try:
                    await server_stack.aclose()
                except BaseException:
                    pass
                if name in self.sessions:
                    del self.sessions[name]

        return new_tools

    async def remove_server(self, name: str):
        """Disconnect an MCP server and remove its tools."""
        # Remove tools
        to_remove = [k for k in self.available_tools if k.startswith(f"{name}.")]
        for k in to_remove:
            del self.available_tools[k]
        if name in self.sessions:
            del self.sessions[name]

        # Remove from mcp-config.json
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            config.get("mcpServers", {}).pop(name, None)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Warning: could not remove server from config: {e}")
        print(f"[{name}] Removed.")

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