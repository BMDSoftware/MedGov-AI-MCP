"""
MCP Client - Generic client for calling MCP servers
"""
import json
import requests
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

try:
    from .registry import MCPService, MCPServiceRegistry
except ImportError:
    from registry import MCPService, MCPServiceRegistry


@dataclass
class ToolCall:
    """Record of a tool call for auditing"""
    service_name: str
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    success: bool = False


#! Client for interacting with MCP servers, it has tool discovery, calling and callback hooks
# this way we can audit tool calls
class MCPClient:

    def __init__(self, registry: MCPServiceRegistry):
        self.registry = registry
        self._callbacks: List[Callable[[str, ToolCall], None]] = []

    def add_callback(self, callback: Callable[[str, ToolCall], None]) -> None:
        """
        Add a callback for tool call events.
        Callback receives (phase, tool_call) where phase is "before" or "after"
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    # if theres a callback error we just ignore it...
    def _notify(self, phase: str, tool_call: ToolCall) -> None:
        for cb in self._callbacks:
            try:
                cb(phase, tool_call)
            except Exception:
                pass

    # discover tools
    def discover_tools(self, service_name: str) -> List[Dict[str, Any]]:

        service = self.registry.get(service_name)
        if not service:
            raise ValueError(f"Service '{service_name}' not found in registry")

        try:
            response = requests.post(
                f"{service.url}/mcp/tools/list",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                tools = result.get("result", {}).get("tools", [])
                tool_names = [t.get("name", "") for t in tools]
                self.registry.update_status(service_name, "online", tool_names)
                return tools
            else:
                self.registry.update_status(service_name, "offline")
                return []

        except requests.RequestException as e:
            self.registry.update_status(service_name, "offline")
            raise ConnectionError(f"Failed to connect to {service_name}: {e}")

    # call tools with arguments, service, the tool name and then respective arguments for the tool
    def call_tool(
        self,
        service_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Call a tool on an MCP server.

        Args:
            service_name: Name of the registered service
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result (parsed JSON if possible)
        """
        service = self.registry.get(service_name)
        if not service:
            raise ValueError(f"Service '{service_name}' not found in registry")

        tool_call = ToolCall(
            service_name=service_name,
            tool_name=tool_name,
            arguments=arguments or {},
        )

        self._notify("before", tool_call)

        try:
            response = requests.post(
                f"{service.url}/mcp/tools/call",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments or {}},
                    "id": 1,
                },
                timeout=30,
            )

            if response.status_code == 200:
                result_json = response.json()
                mcp_result = result_json.get("result", {})
                content = mcp_result.get("content", [])

                # Parse the result
                if content and len(content) > 0:
                    text = content[0].get("text", "")
                    if text:
                        try:
                            tool_call.result = json.loads(text)
                        except json.JSONDecodeError:
                            tool_call.result = text
                    else:
                        tool_call.result = content[0]
                else:
                    tool_call.result = mcp_result

                tool_call.success = True
                self.registry.update_status(service_name, "online")

            else:
                tool_call.error = f"HTTP {response.status_code}: {response.text}"
                tool_call.success = False

        except requests.RequestException as e:
            tool_call.error = str(e)
            tool_call.success = False
            self.registry.update_status(service_name, "offline")

        self._notify("after", tool_call)

        if not tool_call.success:
            raise RuntimeError(f"Tool call failed: {tool_call.error}")

        return tool_call.result


    # make regular health checks (individual service)
    def health_check(self, service_name: str) -> bool:
        service = self.registry.get(service_name)
        if not service:
            return False

        try:
            # Try to list tools as a health check
            self.discover_tools(service_name)
            return True
        except Exception:
            self.registry.update_status(service_name, "offline")
            return False

    # check all services
    def health_check_all(self) -> Dict[str, bool]:
        results = {}
        for service in self.registry.list():
            results[service.name] = self.health_check(service.name)
        return results
