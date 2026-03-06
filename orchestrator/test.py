import asyncio
import os
from pathlib import Path
import time

import yaml
from langchain_mcp_adapters.client import MultiServerMCPClient  
from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, HumanMessage
from langchain.agents import create_agent
from dotenv import load_dotenv
from mem0 import Memory


load_dotenv()

config = {
    "llm": {
        "provider": "gemini",
        "config": {
            "model": "gemini-2.0-flash",
            "temperature": 0.2,
            "max_tokens": 2000,
            "top_p": 1.0
        }
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2" # Small, fast, and local
        }
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "path": ".mem0_data" # Saves your memory to a local folder
        }
    }
}

memory = Memory.from_config(config)
USER_ID = "physician_hemapefe"

# The local path where files live
WORKSPACE_DIR = "/Users/hemapefe/Desktop/AgenticHealthMCP/orchestrator/workspace"
# The URL where your FastAPI/Static server will serve these files
BASE_URL = "http://localhost:8000/files"

async def main():
    # 1. Setup MCP Client (Your existing config)
    client = MultiServerMCPClient({
        "skills": {
            "transport": "stdio",
            "command": "/Users/hemapefe/Desktop/AgenticHealthMCP/.venv/bin/python",
            "args": ["/Users/hemapefe/Desktop/AgenticHealthMCP/mcp-skills/server.py"],
            "env": {"PYTHONUNBUFFERED": "1", "SKILLS_DIR": "/Users/hemapefe/Desktop/AgenticHealthMCP/orchestrator/skills"}
        },
        "utils": {
            "transport": "stdio",
            "command": "/Users/hemapefe/Desktop/AgenticHealthMCP/.venv/bin/python",
            "args": ["/Users/hemapefe/Desktop/AgenticHealthMCP/mcp-utils/server.py"],
            "env": {
                "PYTHONUNBUFFERED": "1"
            }
        },
        "radlex": {
            "transport": "stdio",
            "command": "/Users/hemapefe/Desktop/AgenticHealthMCP/.venv/bin/python",
            "args": ["/Users/hemapefe/Desktop/AgenticHealthMCP/mcp-radlex/server.py"],
            "env": {
                "PYTHONUNBUFFERED": "1"
            }
        },
        "monai": {
            "transport": "stdio",
            "command": "/Users/hemapefe/Desktop/AgenticHealthMCP/mcp-monai/.venv/bin/python",
            "args": ["/Users/hemapefe/Desktop/AgenticHealthMCP/mcp-monai/server.py"],
            "env": {
                "PYTHONUNBUFFERED": "1"
            }
        }
    })

    # 2. Initialize Model
    model = init_chat_model("google_genai:gemini-2.0-flash")
    
    # 3. Get Tools from MCP
    tools = await client.get_tools()  

    query = "DICOM anonymization and metadata extraction"
    previous_memories = memory.search(query, user_id=USER_ID)
    
    # Format memories for the prompt
    memory_context = ""
    
    # 1. Handle cases where Mem0 returns a dict like {"results": [...]} 
    # instead of a raw list
    items = []
    if isinstance(previous_memories, dict):
        items = previous_memories.get("results", [])
    elif isinstance(previous_memories, list):
        items = previous_memories

    if items:
        memory_context = "\n# PREVIOUS CONTEXT (Long-term Memory):\n"
        for m in items:
            if isinstance(m, dict):
                # Check all possible keys Mem0 uses for content
                content = m.get("memory") or m.get("text") or m.get("content")
                if content:
                    memory_context += f"- {content}\n"
                else:
                    # If we can't find a key, show the whole dict for debugging
                    memory_context += f"- {str(m)}\n"
            else:
                memory_context += f"- {str(m)}\n"

    print(f"--- DEBUG: Extracted {len(items)} actual memory items ---")
    print(memory_context)

    # 5. Create the Agent
    # We use a standard LangChain executor to handle the tool loop
    

    # --- SIMULATE THE "FILE DROP" ---
    # In your real app, the frontend drops 'patient_scan.jpg' into the folder
    # and then triggers this call.
    dropped_folder = "/Users/hemapefe/Desktop/AgenticHealthMCP/mcp-monai/sample_data/pancreas_data/1.2.826.0.1.3680043.2.1125.1.68878959984837726447916707551399667"
    
    print(f"\n[Autonomous Trigger] Processing dropped folder: {dropped_folder}")
    
    
    literary_agent = create_agent(
        model,
        tools,
        system_prompt=SystemMessage(
            content=[
                {
                    "type": "text",
                    "text": f"""
        # ROLE
You are a specialized Healthcare AI Assistant. Your operations are strictly bound to the medical context of the current patient provided in the session context. If no patient context is present, ask the user to provide it before proceeding.

{memory_context}
---

# AVAILABLE SKILLS (DIRECTORY)
{load_all_skills()}

Only use skills listed above and tools available in the system. Do not attempt to use, guess, or simulate any skill not present in this directory, same for tools.

---

# SKILL USAGE PROTOCOL

You do not have full skill instructions pre-loaded. You must follow this exact workflow for every clinical task, silently and without narrating your steps to the user:

**Step 1 — IDENTIFY**
Determine which skill from the directory is required. If no skill matches the request, respond:
> "I do not have the specific clinical skill required for this task."
Do not proceed further.

**Step 2 — READ**
Call `skills.read_skill_file(skill_name)` to load the detailed instructions for that skill. Do not execute any domain tools before completing this step.

**Step 3 — EXPLORE (if needed)**
If the SKILL.md references additional schemas or technical files, call `skills.read_references(skill_name, file_path)` to retrieve them before proceeding.

**Step 4 — EXECUTE**
Follow the instructions returned by the skill file precisely. Use the domain tools specified (e.g., `monai.*`, `fhir.*`). If the skill includes executable scripts, call `skills.execute_script(skill_name, script_name, parameters)`.

**Step 5 — INTERPRET & RESPOND**
Treat all tool outputs as raw clinical observations. Apply professional interpretation before presenting findings to the user. For reports, be thorough and specific: include all findings, relevant values, flags, and clinical context. Never present raw tool output without interpretation.

---

# OPERATIONAL RULES

- **One skill at a time.** If a request spans multiple skills, handle each sequentially and silently, completing one before starting the next.
- **No hallucinations.** Never guess, simulate, or infer skill outputs. If a tool returns unexpected or empty data, state this to the user rather than filling gaps with assumptions.
- **Re-read on new tasks.** Do not assume skill instructions are cached between turns. Re-read the SKILL.md for each new task unless the same skill was used in the immediately preceding step of the same task.
- **Skill independence.** Skill outputs do not override your clinical reasoning — you are responsible for interpreting results in the context of the patient's data.
- **Missing patient context.** If required patient data is absent or incomplete, ask the user to provide it before calling any tools.

---

# ERROR HANDLING

- If `skills.read_skill_file()` fails or returns empty: retry once silently, then surface a brief error message to the user if it fails again.
- If a domain tool returns an error code: surface the status to the user concisely without technical jargon.
- If results appear clinically inconsistent or out of expected range: flag this explicitly in your response before providing interpretation.

---

# INTERACTION GUIDELINES

- **Capability questions** ("What can you do?"): Describe the available skills from the directory above. Do not call any tools to answer this.
- **Clinical action requests**: Execute the full 5-step protocol silently. Only speak when you have a final result, a clarifying question, or an error to surface.
- **Ambiguous requests**: Ask one clarifying question before selecting a skill.

---

# SAFETY & EMERGENCY PROTOCOL

- If patient data indicates a potentially critical clinical condition, surface this immediately and clearly before any further analysis.
- If tools fail during a time-sensitive task, surface the failure concisely rather than attempting recovery silently.
- Never delay surfacing critical findings in favor of completing a full analysis."""
,
            }
        ]
    )
)

    # CORRECT (Asynchronous call)
    result = await literary_agent.ainvoke(
        {"messages": [{"role": "user", "content": f"Analyse this {dropped_folder} and make a report with the findings. use spleen model", "type": "thinking"}]}
    )

    print("\n=== AGENT WORKFLOW STEPS ===\n")

    for i, msg in enumerate(result["messages"]):
        # 1. USER INPUT
        if msg.type == "human":
            print(f"STEP {i}: USER REQUEST")
            print(f"{msg.content}\n")

        # 2. AGENT THINKING & ACTIONS
        elif msg.type == "ai":
            # Check if there is "Thinking" text (content)
            if msg.content and not msg.tool_calls:
                print(f"STEP {i}: FINAL SUMMARY")
                print(f"{msg.content}\n")
            
            elif msg.tool_calls:
                print(f"STEP {i}: AGENT REASONING & ACTION")
                # This prints the "Internal Thought" if the model provided one
                if msg.content:
                    print(f"Thought: {msg.content}")
                
                for tool_call in msg.tool_calls:
                    print(f"Tool: {tool_call['name']}")
                    print(f"Args: {tool_call['args']}")
                print("")

        # 3. TOOL RESULTS
        elif msg.type == "tool":
            print(f"STEP {i}: TOOL OUTPUT")
            # This shows exactly what the script returned
            print(f"{msg.content}\n")

    print("============================")

    memory_payload = [
            {
                "role": "user", 
                "content": f"Processed scan {dropped_folder}. Findings: {result['messages'][-1].content if result['messages'] else 'No final summary provided.'}"
            }
        ]
        
    try:
        # Pass the list directly to .add()
        memory.add(memory_payload, user_id=USER_ID, metadata={"file_path": dropped_folder})
        print(f"\n[Mem0] Information stored for User: {USER_ID}")
    except Exception as e:
        print(f"\n[Mem0 Error] Could not save memory: {e}")


def load_all_skills():
        """
        Scans the skills directory, finds SKILL.md files, and loads their metadata.
        Returns formatted text listing available skills for the system prompt.
        """
        skills_text = []
        SKILL_DIR_PATH = Path(__file__).parent / "skills"
        
        if not SKILL_DIR_PATH.exists():
            return "No skills directory found."

        # Iterate through every sub-folder in the root skills directory
        for skill_folder in SKILL_DIR_PATH.iterdir():
            if not skill_folder.is_dir():
                continue
                
            skill_file = skill_folder / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text()
                    # Split YAML frontmatter from Markdown body
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1]
                        metadata = yaml.safe_load(frontmatter)
                        
                        skill_name = metadata.get("name", skill_folder.name)
                        skill_description = metadata.get("description", "No description")
                        skills_text.append(f"- **{skill_name}**: {skill_description}")
                except Exception as e:
                    print(f"Error loading skill {skill_folder.name}: {e}")
        
        return "\n".join(skills_text) if skills_text else "No skills available"


if __name__ == "__main__":
    asyncio.run(main())