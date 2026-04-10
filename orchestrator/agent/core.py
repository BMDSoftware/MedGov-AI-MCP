import json
import logging
from pathlib import Path
from typing import Set

from tool_registry import ToolRegistry
from sessionContext import SessionContext
from logger import Logger

from .constants import LLM_BACKEND
from .prompts import NORMAL_MODE_COMMUNICATION_RULES
from .builtin_tools import BUILTIN_TOOLS
from .tool_management import ToolManagementMixin
from .session import SessionMixin
from .skills import SkillsMixin
from .confirmation import ConfirmationMixin
from .execution import ExecutionMixin
from .formatting import ResultFormattingMixin
from .stm import STMMixin, STM_BUILTIN_TOOLS, AgentStateManager


class AgenticAgent(
    STMMixin,              # first: runs __init__ then chains super()
    ToolManagementMixin,
    SessionMixin,
    SkillsMixin,
    ConfirmationMixin,
    ExecutionMixin,
    ResultFormattingMixin,
):
    """AI agent that decides which MCP tools to call based on context and data."""

    def __init__(self, callback=None, enable_debug_logging=True, log_level=logging.DEBUG):
        self.stm_manager = AgentStateManager()
        self.tool_registry = ToolRegistry()
        self.available_tools = {}
        self.agent_tools: Set[str] = set()
        self.callback = callback
        self.llm_client = None
        self.session_context = SessionContext()
        self.mode = 'debug'
        self.is_agent_autonomous = False
        self.require_confirmation = True
        self.pending_tool_call = None
        self.pending_task_context = None

        self.logger = Logger(name="AgenticAgent", log_level=log_level, is_active=enable_debug_logging)

    async def _initialize_components(self):
        """Initialize LLM client and tool registry with discovered tools."""
        self.logger.info("Initializing agent components...")

        self.available_tools = await self.tool_registry.discover_tools()
        self.available_tools.update(BUILTIN_TOOLS)
        if self._is_stateless_llm_mode():
            self.available_tools.update(STM_BUILTIN_TOOLS)
        self.agent_tools = set(self.available_tools.keys())
        skills = self.load_all_skills()
        enabled_tools = self.get_enabled_agent_tools()

        self.logger.info(f"Discovered {len(self.available_tools)} tools: {list(self.available_tools.keys())}")
        self.logger.info(f"LLM Backend: {LLM_BACKEND}")

        if LLM_BACKEND.lower() == "ollama":
            print("Using Ollama (local) for orchestration")
            from ollama_client import OllamaClient
            self.llm_client = OllamaClient(enabled_tools)
        else:
            print("Using Gemini (API) for orchestration")
            from gemini_client import GeminiClient
            self.llm_client = GeminiClient(enabled_tools, skills)

    def _is_stateless_llm_mode(self) -> bool:
        """Read llm_mode from app settings to decide whether STM tools should be exposed."""
        settings_path = Path(__file__).resolve().parents[1] / "app_settings.json"
        try:
            with open(settings_path) as f:
                return json.load(f).get("llm_mode", "stateful") == "stateless"
        except Exception:
            return False

    async def close(self):
        """Explicit async cleanup for tool registry resources."""
        await self.tool_registry.close()

    def set_mode(self, mode: str):
        """Switch between 'debug' and 'normal' mode."""
        self.mode = mode
        if mode == 'normal':
            self.require_confirmation = False
            if self.llm_client and hasattr(self.llm_client, 'set_mode_extension'):
                self.llm_client.set_mode_extension(NORMAL_MODE_COMMUNICATION_RULES)
        else:
            self.require_confirmation = True
            if self.llm_client and hasattr(self.llm_client, 'set_mode_extension'):
                self.llm_client.set_mode_extension("")
        print(f"[agent] Mode set to '{mode}' (require_confirmation={self.require_confirmation})")

    def set_agent_type(self, autonomous: bool):
        """Set whether the agent is currently executing autonomously."""
        self.is_agent_autonomous = autonomous
        print(f"[agent] Autonomous execution set to {autonomous}")
