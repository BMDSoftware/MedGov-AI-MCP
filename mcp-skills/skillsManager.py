"""
Simplified Tool-Based Skills Workflow

Skills are listed in the system prompt (NOT as LLM function tools).
Agent executes them via internal function routing.
"""

import sys
import re
import json
import subprocess
from unittest import result
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class Skill:
    """Skill metadata from SKILL.md frontmatter."""
    name: str
    description: str
    path: Path


class SkillsManager:
    """Discovers and executes skills."""
    
    def __init__(self, skills_dir: str):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Skill] = {}
        self.skill_cache: Dict[str, Dict[str, Any]] = {}  # Stores full skill activation data
        self.file_cache: Dict[str, str] = {}  # Stores individual skill file content
    
    def discover(self) -> List[Skill]:
        """Find all SKILL.md files and parse metadata."""
        if not self.skills_dir.exists():
            return []
        
        for folder in self.skills_dir.iterdir():
            skill_file = folder / "SKILL.md"
            if folder.is_dir() and skill_file.exists():
                skill = self._parse(skill_file)
                if skill:
                    self.skills[skill.name] = skill
        
        return list(self.skills.values())
    
    def _parse(self, path: Path) -> Optional[Skill]:
        """Extract name/description from YAML frontmatter."""
        try:
            text = path.read_text()
            match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
            if not match:
                return None
            
            front = match.group(1)
            name = re.search(r'name:\s*(.+)', front)
            desc = re.search(r'description:\s*(.+)', front)
            
            if name and desc:
                return Skill(name.group(1).strip(), desc.group(1).strip(), path)
        except Exception as e:
            print(f"Parse error: {e}")
        return None
    
    def to_xml(self) -> str:
        """Generate skills XML for system prompt."""
        if not self.skills:
            return ""
        
        lines = ["<available_skills>"]
        for s in self.skills.values():
            lines += ["  <skill>", f"    <name>{s.name}</name>", 
                     f"    <description>{s.description}</description>", "  </skill>"]
        lines.append("</available_skills>")
        return "\n".join(lines)
    
    def activate(self, name: str) -> Optional[Dict[str, Any]]:
        """Load SKILL.md content and list available helper files (cached).
        
        Returns:
            Dict with 'name', 'content' (SKILL.md text), and 'available_files' (list of paths)
        """
        if name not in self.skills:
            return None
        
        if name not in self.skill_cache:
            skill_content = self.skills[name].path.read_text()
            available_files = self._list_skill_files(name)
            
            self.skill_cache[name] = {
                "name": name,
                "content": skill_content,
                "available_files": available_files
            }
        
        return self.skill_cache[name]
    
    
    def _list_skill_files(self, name: str) -> List[str]:
        """List all files in a skill directory (excluding SKILL.md and hidden files).
        
        Returns relative paths from skill directory root.
        """
        if name not in self.skills:
            return []
        
        skill_dir = self.skills[name].path.parent
        files = []
        
        
        for path in skill_dir.rglob("*"):
            # 3. Filter out hidden files (those starting with '.')
            if path.is_file() and not path.name.startswith('.') and not path.name == "SKILL.md":
                # Get relative path from skill directory
                rel_path = path.relative_to(skill_dir)
                files.append(str(rel_path))
        
        return sorted(files)
    

    
    def load_skill_file(self, name: str, file_path: str) -> Optional[str]:
        """Load a specific file from a skill directory with security validation.
        
        Args:
            name: Skill name
            file_path: Relative path to file within skill directory
            
        Returns:
            File content or None if file doesn't exist or path is invalid
        """
        if name not in self.skills:
            return None
        
        skill_dir = self.skills[name].path.parent
        
        # Construct absolute path and validate it's within skill directory
        try:
            # Resolve to absolute path and check it's within skill_dir
            requested_path = (skill_dir / file_path).resolve()
            
            # Security check: ensure path doesn't escape skill directory
            if not str(requested_path).startswith(str(skill_dir.resolve())):
                print(f"Security: Path '{file_path}' escapes skill directory")
                return None
            
            # Check file exists and is a file (not directory)
            if not requested_path.exists() or not requested_path.is_file():
                return None
            
            # Check cache first
            cache_key = f"{name}:{file_path}"
            if cache_key not in self.file_cache:
                self.file_cache[cache_key] = requested_path.read_text()
            
            return self.file_cache[cache_key]
            
        except (ValueError, OSError) as e:
            print(f"Error loading file '{file_path}' from skill '{name}': {e}")
            return None
    
    def execute(self, name: str, action: str, **params) -> Dict:
        """Execute skill action by dynamically importing and calling Python functions or scripts. 
        """
        if name not in self.skills:
            return {"error": f"Skill '{name}' not found"}
        
        folder = self.skills[name].path.parent
        
        print(f"Folder: {folder}, Action: {action}, Params: {params}")
        # If action is a script filename (ends with .py or .sh), run it directly
        if action.endswith('.py') or action.endswith('.sh'):
            result = self._run_script_direct(folder, action, **params)
            if result is not None:
                return result
            return {"error": f"Script '{action}' not found in skill '{name}'"}
        
        # Otherwise, try to import and call as a function
        result = self._import_and_call(folder, action, **params)
        if result is not None:
            return result
        
        # Fallback: try running as subprocess with action as base name
        result = self._run_script(folder, action, **params)
        if result is not None:
            return result
        
        return {"error": f"No executable found for action '{action}' in skill '{name}'"}
    
    def _run_script_direct(self, folder: Path, script_filename: str, **params) -> Optional[Dict]:
        """Run a script file directly by its filename."""
        script_path = folder / script_filename
        
        if not script_path.exists():
            return None
        
        try:
            if script_filename.endswith('.py'):
                args = [sys.executable, str(script_path)]
            else:
                args = [str(script_path)]
            
            # Add parameters as command line arguments
            for k, v in params.items():
                args.extend([f"--{k}", str(v)])
            
            result = subprocess.run(args, capture_output=True, text=True, 
                                   timeout=30, cwd=str(folder))
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"success": result.returncode == 0, 
                       "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    
    def _import_and_call(self, folder: Path, action: str, **params) -> Optional[Dict]:
        """Dynamically import Python modules and call the action function."""
        # Find all Python files in the folder
        py_files = list(folder.glob("*.py"))
        
        for py_file in py_files:
            if py_file.name.startswith("__"):
                continue
            
            try:
                # Dynamically import the module
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[py_file.stem] = module
                    spec.loader.exec_module(module)
                    
                    # Check if the action function exists in this module
                    if hasattr(module, action):
                        func = getattr(module, action)
                        # Call the function with params
                        result = func(**params)
                        
                        # Ensure result is a dict
                        if isinstance(result, dict):
                            return result
                        else:
                            return {"success": True, "result": result}
            except Exception:
                # Continue to next file if this one fails
                continue
        
        return None
    
    def _run_script(self, folder: Path, action: str, **params) -> Optional[Dict]:
        """Try to execute scripts as subprocess (fallback method)."""
        for script in [f"{action}.py", "run.py", f"{action}.sh"]:
            path = folder / script
            if not path.exists():
                continue
            
            try:
                # Use python to run .py scripts instead of direct execution
                if script.endswith('.py'):
                    args = [sys.executable, str(path), action]
                else:
                    args = [str(path), action]
                
                for k, v in params.items():
                    args.extend([f"--{k}", str(v)])
                
                result = subprocess.run(args, capture_output=True, text=True, 
                                       timeout=30, cwd=str(folder))
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"success": result.returncode == 0, 
                           "stdout": result.stdout, "stderr": result.stderr}
            except Exception as e:
                return {"error": str(e)}
        return None
    

    def read_asset_content(self, name: str, asset_path: str) -> Dict[str, Any]:
        """Reads asset content, handling text vs binary safely."""
        path = self.get_asset_path(name, asset_path)
        if not path or not path.is_file():
            return {"error": "Asset not found"}

        # List of extensions the LLM can safely 'read' as text
        text_extensions = {'.json', '.xml', '.csv', '.txt', '.html', '.md', '.yaml', '.yml', '.tex', '.toml', '.sql'}
        
        if path.suffix.lower() in text_extensions:
            try:
                return {
                    "type": "text",
                    "content": path.read_text(encoding='utf-8'),
                    "path": str(path)
                }
            except Exception as e:
                return {"error": f"Failed to read text asset: {str(e)}"}
        else:
            # For binary files (images, docx, etc.), just return metadata
            return {
                "type": "binary",
                "message": "This is a binary file and cannot be read directly as text. Use a script to process it.",
                "path": str(path),
                "extension": path.suffix,
                "size_bytes": path.stat().st_size
            }

    def get_asset_path(self, name: str, asset_path: str) -> Optional[Path]:
            """Returns the absolute path to an asset for script execution."""
            if name not in self.skills:
                return None
            
            skill_dir = self.skills[name].path.parent
            full_path = (skill_dir / asset_path).resolve()
            
            # Security: check it's inside the skill directory
            if str(full_path).startswith(str(skill_dir.resolve())) and full_path.exists():
                return full_path
            return None


if __name__ == "__main__":
    # Example usage
    skills_dir = Path(__file__).parent / "skills"
    manager = SkillsManager(skills_dir)

    print("--- Discovering Skills ---")
    manager.discover()
    print(manager.to_xml())
    
    print("\n--- Activating Skill ---")
    skill_data = manager.activate("radiology-agentic-reporting")
    if skill_data:
        print(f"Skill: {skill_data['name']}")
        print(f"Content length: {len(skill_data['content'])} chars")
        print(f"Available files: {skill_data['available_files']}")
        
        print("\n--- Loading Helper File ---")
        if skill_data['available_files']:
            first_file = skill_data['available_files'][0]
            content = manager.load_skill_file("radiology-agentic-reporting", first_file)
            if content:
                print(f"Loaded '{first_file}': {len(content)} chars")
                print(f"Preview: {content[:200]}...")
    
    print("\n--- Testing Security (path traversal) ---")
    result = manager.load_skill_file("radiology-agentic-reporting", "../../../etc/passwd")
    print(f"Escape attempt result: {result}")