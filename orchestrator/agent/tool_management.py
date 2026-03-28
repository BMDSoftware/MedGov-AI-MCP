from typing import Dict, Set


class ToolManagementMixin:
    """Enable, disable, and refresh MCP tools and servers."""

    def get_enabled_agent_tools(self) -> Dict[str, Dict]:
        return {name: info for name, info in self.available_tools.items() if name in self.agent_tools}

    def _load_disabled_tools(self) -> Set[str]:
        # Tool state is now stored per-user in the database.
        return set()

    def _save_disabled_tools(self):
        # Tool state is now stored per-user in the database.
        pass

    def enable_tool(self, tool_name: str):
        if tool_name in self.available_tools and tool_name not in self.agent_tools:
            self.agent_tools.add(tool_name)
            self._refresh_agent_components()
            self._save_disabled_tools()
        elif tool_name in self.agent_tools:
            print(f"Tool already enabled: {tool_name}")
        else:
            print(f"Tool not found in available_tools: {tool_name}")

    def disable_tool(self, tool_name: str):
        if tool_name in self.agent_tools:
            self.agent_tools.remove(tool_name)
            self._refresh_agent_components()
            self._save_disabled_tools()
        else:
            print(f"Tool not enabled: {tool_name}")

    def _refresh_agent_components(self):
        enabled_tools = self.get_enabled_agent_tools()
        if self.llm_client:
            self.llm_client.update_tools(enabled_tools)

    async def refresh_server_tools(self, name: str):
        new_tools = await self.tool_registry.refresh_server_tools(name)
        old = [k for k in self.available_tools if k.startswith(f"{name}.")]
        for k in old:
            self.available_tools.pop(k, None)
            self.agent_tools.discard(k)
        self.available_tools.update(new_tools)
        self.agent_tools.update(new_tools.keys())
        self._refresh_agent_components()
        return new_tools

    async def add_mcp_server(self, name: str, cfg: dict):
        new_tools = await self.tool_registry.add_server(name, cfg)
        self.available_tools.update(new_tools)
        self.agent_tools.update(new_tools.keys())
        self._refresh_agent_components()
        return new_tools

    async def remove_mcp_server(self, name: str):
        await self.tool_registry.remove_server(name)
        to_remove = [k for k in self.available_tools if k.startswith(f"{name}.")]
        for k in to_remove:
            self.available_tools.pop(k, None)
            self.agent_tools.discard(k)
        self._refresh_agent_components()

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
