#!/usr/bin/env python3
"""
MCP Skills Server - Provides skill management capabilities for the agentic system
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP

# Add current directory to path to import SkillsManager
sys.path.insert(0, str(Path(__file__).parent))
from skillsManager import SkillsManager


def log(msg: str):
    """Log to stderr to avoid interfering with stdio JSON-RPC protocol"""
    print(msg, file=sys.stderr, flush=True)


mcp = FastMCP("skills")

SKILLS_DIR_PATH = os.getenv("SKILLS_DIR")



# Initialize SkillsManager
skills_manager = SkillsManager(SKILLS_DIR_PATH)
skills_manager.discover()

log(f"Skills server initialized with directory: {SKILLS_DIR_PATH}")
log(f"Discovered {len(skills_manager.skills)} skills")



@mcp.tool()
def read_skill_file(skill_name: str) -> Dict[str, Any]:
    """
    Read the SKILL.md file for a specific skill.
    
    Returns the main skill instructions (SKILL.md content) and a list of available
    helper files that can be loaded separately if needed.
    
    :param skill_name: Name of the skill to read
    """
    log(f"Reading SKILL.md for: {skill_name}")
    
    result = skills_manager.activate(skill_name)
    
    if result is None:
        return {
            "error": f"Skill '{skill_name}' not found",
            "available_skills_list": [s.name for s in skills_manager.skills.values()]
        }
    
    log(f"Read SKILL.md with {len(result['available_files'])} helper files available")
    return result


@mcp.tool()
def read_references(skill_name: str, file_path: str) -> Dict[str, Any]:
    """
    Read a specific reference/helper file from a skill directory.
    
    Use this to load detailed documentation, schemas, or configuration files
    that are referenced in SKILL.md.
    
    :param skill_name: Name of the skill
    :param file_path: Relative path to the file within the skill directory (e.g., "references/pipeline.md")
    """
    log(f"Reading reference file: {skill_name}/{file_path}")
    
    content = skills_manager.load_skill_file(skill_name, file_path)
    
    if content is None:
        return {
            "error": f"File '{file_path}' not found in skill '{skill_name}'",
            "available_files": skills_manager._list_skill_files(skill_name) or []
        }
    
    log(f"Read {len(content)} characters from {file_path}")
    
    return {
        "skill_name": skill_name,
        "file_path": file_path,
        "content": content,
        "length": len(content)
    }


@mcp.tool()
def execute_script(skill_name: str, command: str) -> Dict[str, Any]:
    """
    Execute a command within a skill directory context.
    
    The command should be the full path to the script and any arguments.
    The command will be executed with the skill directory as the working directory.
    
    Examples:
    - "python scripts/extract_metadata.py --file_path /path/to/file.dcm"
    - "bash scripts/anonymize_dicom.sh input.dcm output.dcm"
    
    :param skill_name: Name of the skill (used to determine working directory)
    :param command: Full command to execute including script path and arguments
    """
    log(f"Executing command in {skill_name}: {command}")
    
    import subprocess
    from pathlib import Path
    
    # Get skill directory
    if skill_name not in skills_manager.skills:
        return {
            "error": f"Skill '{skill_name}' not found",
            "available_skills_list": list(skills_manager.skills.keys())
        }
    
    skill = skills_manager.skills[skill_name]
    skill_dir = Path(skills_manager.skills_dir) / skill.name
    
    try:
        # Execute command with skill directory as working directory
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(skill_dir),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        log(f"Command completed with return code: {result.returncode}")
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "error": "Command execution timed out (5 minute limit)",
            "success": False
        }
    except Exception as e:
        return {
            "error": f"Failed to execute command: {str(e)}",
            "success": False
        }


@mcp.tool()
def read_asset(skill_name: str, asset_path: str) -> Dict[str, Any]:
    """
    Read or locate a static asset (template, image, data file) from a skill's assets folder.
    
    If the file is text-based (CSV, JSON, HTML), the content is returned.
    If the file is binary (PNG, DOCX, PDF), metadata and the absolute path are returned
    so it can be passed to 'execute_script'.
    
    :param skill_name: Name of the skill
    :param asset_path: Path to the asset (e.g., "assets/invoice_template.html")
    """
    log(f"Accessing asset: {skill_name}/{asset_path}")
    
    result = skills_manager.read_asset_content(skill_name, asset_path)
    
    if "error" in result:
        # Fallback: help the LLM find the right file
        files = skills_manager._list_skill_files(skill_name)
        asset_files = [f for f in files if f.startswith("assets/")]
        return {
            "error": result["error"],
            "available_assets": asset_files
        }
        
    return result


if __name__ == "__main__":
    log("Starting MCP Skills server...")
    mcp.run(transport="stdio")
