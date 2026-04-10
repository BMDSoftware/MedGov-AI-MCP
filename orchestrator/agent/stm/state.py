from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


@dataclass
class AgentState:
    task: str
    completed_steps: List[str] = field(default_factory=list)
    current_objective: str = ""
    artifacts: List[str] = field(default_factory=list)
    important_facts: Dict[str, Any] = field(
        default_factory=lambda: {"task_constraints": {}, "agent_notes": {}}
    )
    status: str = "in_progress"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
