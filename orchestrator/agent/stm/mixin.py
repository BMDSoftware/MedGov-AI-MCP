"""STMMixin — wires AgentStateManager onto the host via cooperative MI."""
from .manager import AgentStateManager


class STMMixin:
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.stm_manager: AgentStateManager = AgentStateManager()
