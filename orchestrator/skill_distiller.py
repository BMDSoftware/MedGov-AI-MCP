#!/usr/bin/env python3
"""Skill Distiller Agent — LLM-based evaluator that decides whether activated
skills should remain in the main agent's context window."""

import os
import re
from dataclasses import dataclass
from typing import Dict, List

import yaml
from google import genai
from dotenv import load_dotenv

from logger import Logger

load_dotenv()

DISTILLER_MODEL = "gemini-2.0-flash"

EVALUATION_PROMPT = """You are a context optimization agent. Given a skill and the current task state, decide if the skill instructions should remain in the main agent's context.

SKILL NAME: {skill_name}
SKILL DESCRIPTION: {skill_description}

CURRENT GOAL: {goal}

COMPLETED STEPS:
{formatted_steps}

Should this skill's full instructions remain in context? Answer ONLY "YES" or "NO".
- YES if the goal still requires this skill's instructions to complete remaining work
- NO if the skill's purpose has been fulfilled or is not relevant to the current goal"""


@dataclass
class TrackedSkill:
    name: str
    description: str
    tool_result: dict
    activated_at_iteration: int


class SkillDistiller:
    """Tracks activated skills and uses an LLM to decide whether each skill
    should remain in the main agent's context on every iteration."""

    def __init__(self, logger: Logger):
        self.tracked_skills: Dict[str, TrackedSkill] = {}
        self.logger = logger
        self.genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def register_skill(self, skill_name: str, description: str, tool_result: dict, iteration: int) -> None:
        """Track a newly activated skill, storing the original tool output."""
        self.tracked_skills[skill_name] = TrackedSkill(
            name=skill_name,
            description=description,
            tool_result=tool_result,
            activated_at_iteration=iteration,
        )
        self.logger.info(f"[SkillDistiller] REGISTERED: {skill_name} at iteration {iteration}")

    def evaluate(self, goal: str, completed_steps: List[str], iteration: int) -> None:
        """For each tracked skill, ask gemini-2.0-flash if it's still needed.
        Removes skills that are no longer needed."""
        if not self.tracked_skills:
            return

        to_remove = []
        for name, skill in self.tracked_skills.items():
            still_needed = self._ask_llm(name, skill.description, goal, completed_steps)
            if still_needed:
                self.logger.info(f"[SkillDistiller] KEEP: {name} (iteration {iteration})")
            else:
                self.logger.info(f"[SkillDistiller] DROP: {name} (iteration {iteration})")
                to_remove.append(name)

        for name in to_remove:
            del self.tracked_skills[name]

    def get_active_skill_results(self) -> list:
        """Return active skills as (tool_name, tool_result) tuples for re-injection as function_responses."""
        return [
            ("skills.read_skill_file", skill.tool_result)
            for skill in self.tracked_skills.values()
        ]

    def get_context_injection(self) -> str:
        """Return active skill content as labeled text for mem0_context injection."""
        if not self.tracked_skills:
            return ""
        sections = []
        for skill in self.tracked_skills.values():
            content = skill.tool_result.get("content", "") if isinstance(skill.tool_result, dict) else str(skill.tool_result)
            sections.append(
                f"[ACTIVE SKILL REFERENCE — {skill.name}]\n"
                f"Use these instructions to complete the task. This is reference material, not a completed deliverable.\n"
                f"{content}\n"
                f"[END SKILL REFERENCE — {skill.name}]"
            )
        return "\n\n".join(sections)

    def _ask_llm(self, skill_name: str, skill_description: str, goal: str, completed_steps: List[str]) -> bool:
        """Single LLM call: returns True if skill is still needed, False if droppable."""
        formatted_steps = "\n".join(f"- {step}" for step in completed_steps) if completed_steps else "None yet"

        prompt = EVALUATION_PROMPT.format(
            skill_name=skill_name,
            skill_description=skill_description,
            goal=goal,
            formatted_steps=formatted_steps,
        )

        try:
            response = self.genai_client.models.generate_content(
                model=DISTILLER_MODEL,
                contents=prompt,
            )
            answer = response.text.strip().upper() if response.text else "YES"
            self.logger.info(f"[SkillDistiller] LLM verdict for '{skill_name}': {answer}")
            return "NO" not in answer
        except Exception as e:
            self.logger.error(f"[SkillDistiller] LLM evaluation failed for '{skill_name}': {e}")
            return True  # Default to keeping the skill on error

    @staticmethod
    def extract_description(content: str) -> str:
        """Parse YAML frontmatter from SKILL.md to extract the description field."""
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1])
                if isinstance(metadata, dict):
                    return metadata.get("description", "")
            except yaml.YAMLError:
                pass
        # Fallback: grab the first non-empty line after frontmatter
        lines = re.split(r"---\s*\n", content, maxsplit=2)
        body = lines[-1] if len(lines) > 1 else content
        for line in body.strip().splitlines():
            stripped = line.strip().lstrip("# ")
            if stripped:
                return stripped[:120]
        return ""
