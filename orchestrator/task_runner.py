"""
Background task runner for long-running operations.

Each task is submitted to a thread pool. The thread spins up its own asyncio
event loop and a fresh MCP session so it doesn't share state with the main
agent. On completion the thread writes the result to the DB and pushes an SSE
event back to the frontend via the main loop's queue.
"""

import asyncio
import json
import os
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))
import database as db

# ── Module-level state ────────────────────────────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="task_worker")


def init():
    """Called once at backend startup."""
    pass  # nothing to initialise — SSE reads task status directly from the DB


# ── Public API ────────────────────────────────────────────────────────────────

def submit_task(session_id: str, task_type: str, description: str, input_data: Dict) -> str:
    """
    Create a DB record for the task and hand it off to the thread pool.
    Returns the task_id immediately so the agent can respond to the user.
    """
    task_id = db.create_task(session_id, task_type, description, input_data)
    _executor.submit(_run_task, task_id, task_type, description, input_data, session_id)
    print(f"[task_runner] Queued {task_type} task {task_id[:8]}: {description}")
    return task_id


# ── Internal task execution ───────────────────────────────────────────────────

def _unwrap_exception_message(e: Exception) -> str:
    """Recursively unwrap ExceptionGroup (raised by anyio/asyncio task groups) to get
    the innermost meaningful error message."""
    if hasattr(e, 'exceptions') and e.exceptions:
        for sub in e.exceptions:
            msg = _unwrap_exception_message(sub)
            if msg:
                return msg
    return str(e)


def _run_task(task_id: str, task_type: str, description: str, input_data: Dict, session_id: str):
    """Entry point for each worker thread."""
    print(f"[task_runner] Starting {task_id[:8]} ({task_type})")
    db.update_task(task_id, "running")

    try:
        handler = _HANDLERS.get(task_type)
        if not handler:
            raise ValueError(f"No handler registered for task type '{task_type}'")

        result = handler(input_data, session_id)
        db.update_task(task_id, "done", result=result)
        print(f"[task_runner] Done {task_id[:8]}")

    except Exception as e:
        # anyio wraps exceptions raised inside async task groups into ExceptionGroup;
        # unwrap recursively to get the actual root cause message for the LLM
        technical_err = _unwrap_exception_message(e)
        print(f"[task_runner] Failed {task_id[:8]}: {technical_err}")
        traceback.print_exc()

        if task_type == "inference":
            friendly_err = _explain_inference_error(technical_err, input_data)
        else:
            friendly_err = technical_err

        db.update_task(task_id, "failed", error=friendly_err)


# ── Handler: inference ────────────────────────────────────────────────────────

def _handle_inference(input_data: Dict, session_id: str) -> Dict:
    """
    Run MONAI inference via a fresh MCP session opened in this thread's event loop.
    input_data: {image_path, model_name}
    """
    image_path = input_data["image_path"]
    model_name = input_data["model_name"]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_async_run_inference(image_path, model_name))
    finally:
        loop.close()


async def _async_run_inference(image_path: str, model_name: str) -> Dict:
    """Open a fresh MCP session to the MONAI server and run inference."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from contextlib import AsyncExitStack

    config_path = Path(__file__).parent / "mcp-config.json"
    with open(config_path) as f:
        config = json.load(f)

    monai_cfg = config["mcpServers"]["monai"]
    params = StdioServerParameters(
        command=monai_cfg["command"],
        args=monai_cfg.get("args", []),
        env={**os.environ, **monai_cfg.get("env", {})},
    )

    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        mcp_result = await session.call_tool(
            "run_inference",
            arguments={"image_path": image_path, "model_name": model_name},
        )

        combined = "".join(
            block.text for block in mcp_result.content if hasattr(block, "text")
        )
        try:
            result = json.loads(combined)
        except (json.JSONDecodeError, TypeError):
            return {"text": combined}

        # If MONAI returned an error dict, raise so _run_task marks this task as failed
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])

        return result


def _explain_inference_error(technical_error: str, input_data: Dict) -> str:
    """Call the LLM to generate a plain-language explanation of an inference failure."""
    model_name = input_data.get("model_name", "unknown model")
    image_path = input_data.get("image_path", "")
    image_filename = os.path.basename(image_path) if image_path else "unknown file"

    prompt = (
        "A medical imaging AI failed to analyse a scan. "
        "Explain the error below to a radiologist in 2-3 plain English sentences. "
        "Do not use Python, programming, or technical computing terms. "
        "State clearly what went wrong and what the radiologist should do instead.\n\n"
        f"Technical error: {technical_error}\n"
        f"Model: {model_name}\n"
        f"Image file: {image_filename}\n\n"
        "Respond with plain text only, no bullet points, no markdown."
    )

    llm_backend = os.getenv("LLM_BACKEND", "gemini")
    try:
        if llm_backend.lower() == "ollama":
            import requests
            ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            resp = requests.post(
                f"{ollama_url}/api/generate",
                json={"model": ollama_model, "prompt": prompt, "stream": False},
                timeout=30,
            )
            explanation = resp.json().get("response", "").strip()
        else:
            from google import genai as google_genai
            from dotenv import load_dotenv
            load_dotenv()
            client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            model_id = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            response = client.models.generate_content(model=model_id, contents=prompt)
            explanation = (response.text or "").strip()

        if explanation:
            return explanation
    except Exception as e:
        print(f"[task_runner] LLM error explanation failed: {e}")

    # Fallback to raw technical error if LLM call fails
    return technical_error


# ── Handler: report ───────────────────────────────────────────────────────────

def _handle_report(input_data: Dict, session_id: str) -> Dict:
    """
    Generate a structured radiology report from completed inference task results.

    Flow:
      1. Gather inference results from DB
      2. Find a matching RadLex template via MCP
      3. Fill the template with the quantitative findings
      4. Augment with LLM-generated Impression / Recommendations

    input_data: {task_ids: [...], patient_context: {...}}
    """
    task_ids = input_data.get("task_ids", [])
    patient_context = input_data.get("patient_context", {})

    tasks = [db.get_task(tid) for tid in task_ids]
    tasks = [t for t in tasks if t and t.get("status") == "done"]
    if not tasks:
        raise ValueError("No completed tasks found for the given task IDs")

    # Build structured findings list from inference results
    findings = []
    modalities = set()
    body_parts = set()
    for task in tasks:
        result = task.get("result", {}) or {}
        detected = result.get("results", {}).get("detected_structures", [])
        model_used = result.get("model_used", "unknown")
        findings.append({
            "description": task["description"],
            "model": model_used,
            "input_image": result.get("input_image", ""),
            "structures": detected,
        })
        # Collect modality / body_part hints for template search
        inp = task.get("input_data", {}) or {}
        if inp.get("model_name"):
            # Map known models to search terms
            m = inp["model_name"]
            if "ct" in m.lower():
                modalities.add("CT")
            if "mri" in m.lower() or "brats" in m.lower():
                modalities.add("MRI")
            if "whole" in m.lower():
                body_parts.add("whole body")
            elif "spleen" in m.lower() or "abdomen" in m.lower() or "pancreas" in m.lower():
                body_parts.add("abdomen")
            elif "lung" in m.lower() or "chest" in m.lower():
                body_parts.add("chest")
            elif "brain" in m.lower() or "brats" in m.lower():
                body_parts.add("brain")

    # Try to use RadLex to find and fill a report template
    radlex_report = None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        query = " ".join(list(modalities) + list(body_parts)) or "CT abdomen"
        radlex_report = loop.run_until_complete(
            _async_radlex_report(query, findings, patient_context)
        )
    except Exception as e:
        print(f"[task_runner] RadLex report failed ({e}), falling back to LLM only")
    finally:
        loop.close()

    narrative = _generate_report_narrative(findings, patient_context)

    return {
        "patient_context": patient_context,
        "findings": findings,
        "radlex_template": radlex_report,   # structured template output (may be None)
        "narrative": narrative,             # LLM-generated sections
        "generated_at": datetime.now().isoformat(),
    }


async def _async_radlex_report(query: str, findings: list, patient_context: Dict) -> Optional[Dict]:
    """Open a fresh MCP session to RadLex and fill a template with the findings."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from contextlib import AsyncExitStack

    config_path = Path(__file__).parent / "mcp-config.json"
    with open(config_path) as f:
        config = json.load(f)

    radlex_cfg = config["mcpServers"]["radlex"]
    params = StdioServerParameters(
        command=radlex_cfg["command"],
        args=radlex_cfg.get("args", []),
        env={**os.environ, **radlex_cfg.get("env", {})},
    )

    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        # 1. Find matching templates
        find_result = await session.call_tool(
            "find_templates", arguments={"query": query}
        )
        templates_text = "".join(
            b.text for b in find_result.content if hasattr(b, "text")
        )
        templates = json.loads(templates_text) if templates_text else []

        if not templates:
            return None

        # Pick the first result
        template_id = templates[0].get("id") or templates[0].get("template_id")
        if not template_id:
            return None

        # 2. Build a flat findings dict to pass to the template
        flat_findings: Dict[str, Any] = {}
        if patient_context:
            flat_findings["patient"] = patient_context
        for f in findings:
            for s in f.get("structures", []):
                key = s["name"].replace(" ", "_")
                flat_findings[key] = (
                    f"{s['volume_cm3']} cm³" if s.get("volume_cm3") is not None
                    else f"{s['voxel_count']:,} voxels"
                )

        # 3. Fill the template
        gen_result = await session.call_tool(
            "generate_report",
            arguments={"template_id": template_id, "findings": flat_findings},
        )
        gen_text = "".join(b.text for b in gen_result.content if hasattr(b, "text"))
        try:
            return json.loads(gen_text)
        except (json.JSONDecodeError, TypeError):
            return {"raw": gen_text}


def _generate_report_narrative(findings: list, patient_context: Dict) -> Dict:
    """Call the LLM to write Findings narrative, Impression, and Recommendations."""
    findings_text = ""
    for f in findings:
        findings_text += f"\nStudy: {f['description']} (model: {f['model']})\n"
        for s in f.get("structures", []):
            if s.get("volume_cm3") is not None:
                vol = f"{s['volume_cm3']} cm³"
            else:
                vol = f"{s['voxel_count']:,} voxels"
            findings_text += f"  - {s['name']}: {vol} ({s['volume_percentage']:.2f}% of scan)\n"

    prompt = f"""You are a board-certified radiologist writing a structured clinical radiology report based on AI segmentation quantification. Use formal, precise medical language consistent with published radiology reporting guidelines (ACR/RSNA).

Patient context: {json.dumps(patient_context) if patient_context else "Not provided"}

Quantitative AI segmentation findings:
{findings_text}

Instructions:
- FINDINGS: Describe each segmented structure by name, measured volume (in cm³ where available), and percentage of the total scan volume. Note any structure that appears enlarged, reduced, or absent compared to typical reference ranges. Use anatomical terminology (e.g., "The spleen measures X cm³, which is within/above/below the normal range of 100-350 cm³"). If background percentage is near 100%, explicitly state that no target structures were confidently detected and that manual review is warranted.
- IMPRESSION: 2-3 concise sentences. State the primary finding, its likely clinical significance, and overall study adequacy. If the segmentation model detected nothing, flag this as a potentially unreliable result.
- RECOMMENDATIONS: Specific, actionable next steps (e.g., correlation with clinical symptoms, follow-up imaging modality/timeline, biopsy consideration). If findings are normal/unremarkable, state "No further imaging follow-up required at this time."

Respond with valid JSON only, with exactly these keys: "findings_narrative", "impression", "recommendations"."""

    llm_backend = os.getenv("LLM_BACKEND", "gemini")
    text = ""

    try:
        if llm_backend.lower() == "ollama":
            import requests
            ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            resp = requests.post(
                f"{ollama_url}/api/generate",
                json={"model": ollama_model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            text = resp.json().get("response", "")
        else:
            from google import genai as google_genai
            from dotenv import load_dotenv
            load_dotenv()
            client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            model_id = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            response = client.models.generate_content(model=model_id, contents=prompt)
            text = response.text or ""

        # Extract JSON from response
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())

    except Exception as e:
        print(f"[task_runner] LLM narrative failed: {e}")

    # Fallback plain sections
    return {
        "findings_narrative": "AI segmentation completed. See quantitative findings above.",
        "impression": "Automated segmentation performed. Clinical correlation recommended.",
        "recommendations": "Review findings in clinical context.",
    }


# ── Handler registry ──────────────────────────────────────────────────────────

_HANDLERS: Dict[str, Callable] = {
    "inference": _handle_inference,
    "report": _handle_report,
}
