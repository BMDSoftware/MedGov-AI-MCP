"""STM built-in tool schemas — pure data, no execution logic."""
from typing import Dict

STM_BUILTIN_TOOLS: Dict[str, Dict] = {
    "update_agent_notes": {
        "description": (
            "Store a finding or fact in your persistent notes for this task. "
            "Use this after EVERY tool result to capture ALL data you will need later — "
            "numeric values, measurements, identifiers, file paths, names, statuses, errors. "
            "Notes persist across all iterations and are your only long-term memory — anything "
            "not noted here will be lost. Write the actual data, not vague summaries."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short label, e.g. 'spleen_volume_cm3'."},
                "value": {"type": "string", "description": "The fact or finding to remember."},
            },
            "required": ["key", "value"],
        },
        "server": "__builtin__",
        "original_name": "update_agent_notes",
        "transport": "builtin",
    },
    "set_next_objective": {
        "description": (
            "Declare what you will do next to make progress toward the goal. "
            "Call this after each tool result to set your next working objective. "
            "Should be a concise action statement describing your immediate next step."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "objective": {"type": "string", "description": "e.g. 'Run spleen segmentation on the CT volume'."},
            },
            "required": ["objective"],
        },
        "server": "__builtin__",
        "original_name": "set_next_objective",
        "transport": "builtin",
    },
}
