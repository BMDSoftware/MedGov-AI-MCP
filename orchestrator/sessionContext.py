
from datetime import datetime
from typing import List, Dict, Any, Optional

class SessionContext:
    """Accumulates structured tool results across queries so the agent has memory."""

    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self.current_patient: Optional[Dict] = None
        self._max_entries = 50

    def record(self, tool_name: str, result_summary: str, key_data: Dict[str, Any]):
        """Store a condensed record of a successful tool execution."""
        self.entries.append({
            "tool": tool_name,
            "summary": result_summary,
            "data": key_data,
            "timestamp": datetime.now().isoformat()
        })
        if len(self.entries) > self._max_entries:
            self.entries = self.entries[-self._max_entries:]

    def build_context_string(self) -> str:
        """Build a concise text block to inject into prompts."""
        if not self.entries:
            return ""

        lines = ["# SESSION CONTEXT (previous interactions this session)"]
        for i, entry in enumerate(self.entries, 1):
            lines.append(f"{i}. [{entry['tool']}] {entry['summary']}")
            if entry["data"]:
                for k, v in entry["data"].items():
                    if v is None:
                        continue
                    val_str = str(v)
                    if len(val_str) > 200:
                        val_str = val_str[:200] + "..."
                    lines.append(f"   {k}: {val_str}")
        return "\n".join(lines)

    def clear(self):
        """Reset all session context."""
        self.entries.clear()
        self.current_patient = None

    def set_patient(self, patient_id: str, patient_name: str):
        """Set patient focus. Clears context if patient changes."""
        if self.current_patient and self.current_patient["id"] != patient_id:
            self.clear()
        self.current_patient = {"id": patient_id, "name": patient_name}
