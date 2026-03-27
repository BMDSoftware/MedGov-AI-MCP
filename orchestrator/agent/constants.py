import os
from pathlib import Path

# LLM Backend selection: "ollama" (local) or "gemini" (API)
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")

SKILL_DIR_PATH = Path(__file__).resolve().parent.parent / "skills"

_DISABLED_TOOLS_FILE = Path(__file__).resolve().parent.parent / "data" / "disabled_tools.json"
