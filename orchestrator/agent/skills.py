import re

from .constants import SKILL_DIR_PATH


class SkillsMixin:
    """Loads skill metadata from the skills directory."""

    def load_all_skills(self):
        """
        Scans the skills directory, finds SKILL.md files, and loads their metadata.
        Returns formatted text listing available skills for the system prompt.
        """
        skills_text = []

        if not SKILL_DIR_PATH.exists():
            return "No skills directory found."

        for skill_folder in SKILL_DIR_PATH.iterdir():
            if not skill_folder.is_dir():
                continue

            skill_file = skill_folder / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text()
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
                        desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)

                        skill_name = name_match.group(1).strip().strip('"') if name_match else skill_folder.name
                        skill_description = desc_match.group(1).strip().strip('"') if desc_match else "No description"
                        skills_text.append(f"- **{skill_name}**: {skill_description}")
                except Exception as e:
                    print(f"Error loading skill {skill_folder.name}: {e}")

        if not skills_text:
            return "No skills available"
        header = f"Skills directory: `{SKILL_DIR_PATH}`\n"
        return header + "\n".join(skills_text)
