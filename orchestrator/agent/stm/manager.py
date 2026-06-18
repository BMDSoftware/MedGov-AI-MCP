from __future__ import annotations
import json
import os
import re
from typing import Any, List, Optional

from .state import AgentState


class AgentStateManager:
    """Owns and mutates AgentState across agentic loop iterations.
    No imports from the rest of the agent package.
    """

    NOTE_BUDGET_TOKENS: int = 1000

    def __init__(self) -> None:
        self.state: Optional[AgentState] = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def init_state(self, task: str, data: Any, image_paths: List[str]) -> AgentState:
        constraints = {"patient_data_available": True} if data else {}
        initial_artifacts = [p for p in image_paths if isinstance(p, str) and os.path.isdir(p)]
        self.state = AgentState(
            task=task,
            completed_steps=[],
            current_objective="",
            artifacts=initial_artifacts,
            important_facts={"task_constraints": constraints, "agent_notes": {}},
            status="in_progress",
        )
        return self.state

    # ------------------------------------------------------------------ #
    # Context rendering                                                    #
    # ------------------------------------------------------------------ #

    def render_state_context(self) -> str:
        if self.state is None:
            return ""
        parts = ["## AGENT STATE\n", self.state.to_json()]
        return "\n".join(parts)

    def render_state_text(self) -> str:
        """Render state as plain text bullets for prompt inclusion."""
        if self.state is None:
            return ""

        lines = [
            "## AGENT STATE",
            f"Task: {self.state.task}",
            f"Status: {self.state.status}",
            f"Current Objective: {self.state.current_objective or '(not set yet)'}",
        ]

        if self.state.completed_steps:
            lines.append("\nCompleted Steps:")
            for idx, step in enumerate(self.state.completed_steps, 1):
                lines.append(f"{idx}. {step}")

        if self.state.artifacts:
            lines.append("\nArtifacts:")
            for artifact in self.state.artifacts:
                lines.append(f"- {artifact}")

        constraints = self.state.important_facts.get("task_constraints", {})
        if constraints:
            lines.append("\nTask Constraints:")
            for key, value in constraints.items():
                lines.append(f"- {key}: {value}")

        notes = self.state.important_facts.get("agent_notes", {})
        lines.append("\nAgent Notes:")
        if notes:
            for key, value in notes.items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- (none yet)")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # State mutation: automatic (post-tool)                                #
    # ------------------------------------------------------------------ #

    def update_after_tool(self, tool_name: str, result: Any, success: bool, summary: str) -> None:
        if self.state is None:
            return
        prefix = "Completed" if success else "Failed"
        self.state.completed_steps.append(f"{prefix}: {tool_name} — {summary}")
        for path in self._extract_artifacts(result):
            if path not in self.state.artifacts:
                self.state.artifacts.append(path)
        self._prune_notes()

    def _extract_artifacts(self, result: Any) -> List[str]:
        result_str = json.dumps(result) if not isinstance(result, str) else result
        raw = re.findall(r'(/(?:[\w.\-_]+/?)+)', result_str)
        seen: set = set()
        deduped: List[str] = []
        for p in raw:
            path = p.rstrip('"\'\\,;)]}')
            if not path or path in seen:
                continue
            if os.path.isdir(path):
                seen.add(path)
                deduped.append(path)
        return deduped

    # ------------------------------------------------------------------ #
    # State mutation: LLM-initiated                                        #
    # ------------------------------------------------------------------ #

    def update_agent_notes(self, key: str, value: str) -> None:
        if self.state is None:
            return
        self.state.important_facts["agent_notes"][key] = value
        self._prune_notes()

    def set_next_objective(self, objective: str) -> None:
        if self.state is None:
            return
        self.state.current_objective = objective

    # ------------------------------------------------------------------ #
    # Note pruning                                                         #
    # ------------------------------------------------------------------ #

    def _prune_notes(self) -> None:
        if self.state is None:
            return
        notes = self.state.important_facts.get("agent_notes", {})
        while notes and len(json.dumps(notes)) // 4 > self.NOTE_BUDGET_TOKENS:
            oldest_key = next(iter(notes))
            del notes[oldest_key]

