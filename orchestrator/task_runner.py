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
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))
import database as db

# ── Module-level state ────────────────────────────────────────────────────────

def _detect_gpu() -> bool:
    """Return True if an NVIDIA GPU is available on this host."""
    import subprocess
    try:
        return subprocess.run(["nvidia-smi"], capture_output=True, timeout=5).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

_GPU_AVAILABLE = _detect_gpu()
_DEVICE_LABEL = "GPU" if _GPU_AVAILABLE else "CPU"

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="task_worker")

# Inference tasks are CPU/memory heavy (loads a multi-GB model + sliding window).
# Running more than one at a time causes OOM → subprocess crash → "Connection closed".
# This semaphore serialises inference so they queue and run one at a time.
_inference_semaphore = threading.Semaphore(1)

# Cellpose tasks load a neural network model per run and can be memory-intensive,
# especially on GPU. Serialise them to avoid OOM when multiple users submit at once.
_cellpose_semaphore = threading.Semaphore(1)

# Task IDs that have been requested to cancel.
_cancelled_tasks: set = set()

# Maps task_id -> (event_loop, asyncio.Task) for tasks currently executing async work.
# Used to cancel the subprocess by cancelling the asyncio task from another thread.
_running_async_tasks: Dict[str, tuple] = {}


def cancel_task(task_id: str):
    """Cancel a task. Queued tasks will not start. Running tasks have their
    asyncio task cancelled, which closes the MCP subprocess immediately."""
    _cancelled_tasks.add(task_id)
    db.update_task(task_id, "cancelled", error="Cancelled by user")
    entry = _running_async_tasks.get(task_id)
    if entry:
        loop, async_task = entry
        loop.call_soon_threadsafe(async_task.cancel)


def init():
    """Called once at backend startup. Mark any tasks left in queued/running state
    (from a previous process) as failed — they will never complete now."""
    conn = db._get_conn()
    conn.execute(
        "UPDATE background_tasks SET status = 'failed', error = 'Server restarted while task was in progress' "
        "WHERE status IN ('queued', 'running')"
    )
    conn.commit()
    conn.close()


# ── Public API ────────────────────────────────────────────────────────────────

def submit_task(session_id: str, task_type: str, description: str, input_data: Dict) -> str:
    """
    Create a DB record for the task and hand it off to the thread pool.
    Returns the task_id immediately so the agent can respond to the user.
    """
    task_id = db.create_task(session_id, task_type, description, input_data)
    # Inject task_id so inference handler can update status after acquiring semaphore
    enriched = {**input_data, "_task_id": task_id}
    _executor.submit(_run_task, task_id, task_type, description, enriched, session_id)
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
    # Inference tasks delay the 'running' status until the semaphore is acquired
    if task_type not in ("inference", "cellpose"):
        db.update_task(task_id, "running")

    try:
        if task_id in _cancelled_tasks:
            _cancelled_tasks.discard(task_id)
            return

        handler = _HANDLERS.get(task_type)
        if not handler:
            raise ValueError(f"No handler registered for task type '{task_type}'")

        result = handler(input_data, session_id)
        # Handler may return {} when task was cancelled mid-run
        if task_id in _cancelled_tasks:
            _cancelled_tasks.discard(task_id)
            print(f"[task_runner] Cancelled {task_id[:8]}")
            return
        db.update_task(task_id, "done", result=result)
        print(f"[task_runner] Done {task_id[:8]}")

    except asyncio.CancelledError:
        # Asyncio task cancelled by cancel_task() — status already set to 'cancelled'
        _cancelled_tasks.discard(task_id)
        print(f"[task_runner] Cancelled (CancelledError) {task_id[:8]}")

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

    Inference is serialised by _inference_semaphore — only one runs at a time to
    prevent OOM from loading multiple large models simultaneously.
    While waiting for the semaphore the task stays in 'queued' status so the UI
    shows it correctly.
    """
    image_path = input_data["image_path"]
    model_name = input_data["model_name"]

    task_id = input_data.get("_task_id")

    # Wait for exclusive access — stay in 'queued' until we actually start
    _inference_semaphore.acquire()
    if task_id in _cancelled_tasks:
        _inference_semaphore.release()
        return {}
    if task_id:
        db.update_task(task_id, "running")
        print(f"[task_runner] Semaphore acquired, running inference {task_id[:8]}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        coro_task = loop.create_task(_async_run_inference(image_path, model_name))
        if task_id:
            _running_async_tasks[task_id] = (loop, coro_task)
        try:
            return loop.run_until_complete(coro_task)
        except asyncio.CancelledError:
            raise
        finally:
            _running_async_tasks.pop(task_id, None)
            loop.close()
    finally:
        _inference_semaphore.release()


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
        command=os.path.expandvars(monai_cfg["command"]),
        args=[os.path.expandvars(a) for a in monai_cfg.get("args", [])],
        env={**os.environ, **monai_cfg.get("env", {})},
    )

    # Redirect MONAI subprocess stderr to a rolling log file so crash output
    # is visible via /api/diagnostics even when we can't SSH into the container.
    stderr_log = Path(__file__).parent / "data" / "monai_inference_stderr.log"
    stderr_log.parent.mkdir(parents=True, exist_ok=True)

    with open(stderr_log, "a") as _errfp:
        _errfp.write(f"\n--- inference start: {model_name} ---\n")

    async with AsyncExitStack() as stack:
        errlog = open(stderr_log, "a")  # noqa: WPS515, kept open for subprocess lifetime
        stack.callback(errlog.close)
        read, write = await stack.enter_async_context(stdio_client(params, errlog=errlog))
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
        "A medical imaging AI inference job failed. "
        "Explain the error to a technical user in 2-3 sentences. "
        "State the specific technical reason it failed (include the actual error message), "
        "what it means in plain terms, and what the user should do to fix or work around it. "
        "Be accurate and specific — do not generalise or omit the real cause.\n\n"
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
        "radlex_template": radlex_report,
        "narrative": narrative,
        "generated_at": datetime.now().isoformat(),
    }


async def _async_radlex_report(query: str, findings: list, patient_context: Dict) -> Optional[Dict]:
    """Open a fresh MCP session to RadLex (with sampling) and fill a template."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from contextlib import AsyncExitStack
    from sampling_handler import make_sampling_handler

    config_path = Path(__file__).parent / "mcp-config.json"
    with open(config_path) as f:
        config = json.load(f)

    radlex_cfg = config["mcpServers"]["radlex"]
    params = StdioServerParameters(
        command=os.path.expandvars(radlex_cfg["command"]),
        args=[os.path.expandvars(a) for a in radlex_cfg.get("args", [])],
        env={**os.environ, **radlex_cfg.get("env", {})},
    )

    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(
            ClientSession(read, write, sampling_callback=make_sampling_handler())
        )
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

        template_id = templates[0].get("id") or templates[0].get("template_id")
        if not template_id:
            return None

        # 2. Pass raw findings so the server-side sampling does the mapping
        gen_result = await session.call_tool(
            "generate_report",
            arguments={
                "template_id": template_id,
                "inference_results": findings,
                "patient_context": patient_context,
                "specialty": "general",
            },
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


# ── Handler: cellpose ─────────────────────────────────────────────────────────

def _handle_cellpose(input_data: Dict, session_id: str) -> Dict:
    """
    Run Cellpose cell segmentation via a fresh MCP session in this thread's event loop.
    input_data: {image_path, model_type, ...any other segment_cells_2d params}

    Serialised by _cellpose_semaphore — only one run at a time to prevent OOM
    when multiple users submit concurrent segmentation tasks.
    """
    image_path = input_data["image_path"]
    # Cellpose v4 only supports cpsam — force it regardless of what the agent requested
    model_type = "cpsam"
    task_id = input_data.get("_task_id")

    _cellpose_semaphore.acquire()
    if task_id in _cancelled_tasks:
        _cellpose_semaphore.release()
        return {}
    if task_id:
        db.update_task(task_id, "running", message=f"Loading model ({_DEVICE_LABEL})...")
        print(f"[task_runner] Cellpose semaphore acquired, running {task_id[:8]} ({_DEVICE_LABEL})")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        _MAX_CELLPOSE_SECS = 30 * 60  # 30 minutes hard cap

        async def _run():
            if task_id:
                msg = (
                    f"Running model ({_DEVICE_LABEL})..."
                    if _GPU_AVAILABLE
                    else "Running model (CPU - this may take several minutes)..."
                )
                db.update_task(task_id, "running", message=msg)
            try:
                return await asyncio.wait_for(
                    _async_run_cellpose(image_path, model_type, input_data),
                    timeout=_MAX_CELLPOSE_SECS,
                )
            except asyncio.TimeoutError:
                raise RuntimeError(f"Cellpose inference timed out after {_MAX_CELLPOSE_SECS // 60} minutes.")

        coro_task = loop.create_task(_run())
        if task_id:
            _running_async_tasks[task_id] = (loop, coro_task)
        try:
            return loop.run_until_complete(coro_task)
        except asyncio.CancelledError:
            raise
        finally:
            _running_async_tasks.pop(task_id, None)
            loop.close()
    finally:
        _cellpose_semaphore.release()



async def _async_run_cellpose(image_path: str, model_type: str, input_data: Dict) -> Dict:
    """Open a fresh MCP session to the Cellpose server and run segmentation."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from contextlib import AsyncExitStack

    config_path = Path(__file__).parent / "mcp-config.json"
    with open(config_path) as f:
        config = json.load(f)

    cellpose_cfg = config["mcpServers"]["cellpose"]
    params = StdioServerParameters(
        command=os.path.expandvars(cellpose_cfg["command"]),
        args=[os.path.expandvars(a) for a in cellpose_cfg.get("args", [])],
        env={**os.environ, **cellpose_cfg.get("env", {})},
    )

    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        # Build a unique output path that includes the model name so concurrent
        # runs on the same image with different models don't overwrite each other.
        # Always use .png for masks — JPEG is lossy and corrupts integer cell labels.
        p = Path(image_path)
        unique_output = str(p.parent / f"{p.stem}_{model_type}_masks.png")

        arguments = {
            "image_path": image_path,
            "model_type": model_type,
            "output_path": unique_output,
            # gpu is intentionally omitted — server.py auto-detects GPU at startup
            # and sets CUDA_VISIBLE_DEVICES accordingly; cellpose will use GPU if available.
        }
        # Agent-provided params override the defaults above
        for key in ("diameter", "channels", "flow_threshold", "cellprob_threshold", "min_size", "output_path"):
            if key in input_data:
                arguments[key] = input_data[key]

        mcp_result = await session.call_tool("segment_cells_2d", arguments=arguments)

        combined = "".join(
            block.text for block in mcp_result.content if hasattr(block, "text")
        )
        try:
            result = json.loads(combined)
        except (json.JSONDecodeError, TypeError):
            return {"text": combined}

        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])

        # Generate overlay image (outlines drawn on original) for display in the Results tab.
        # Hard 60s timeout — outlines_list can be slow on large images but should never
        # block indefinitely. If it times out we skip the overlay and return masks only.
        if isinstance(result, dict) and "output_path" in result:
            try:
                overlay_result = await asyncio.wait_for(
                    session.call_tool(
                        "save_overlay",
                        arguments={"image_path": image_path, "mask_path": result["output_path"]},
                    ),
                    timeout=60.0,
                )
                overlay_combined = "".join(
                    block.text for block in overlay_result.content if hasattr(block, "text")
                )
                overlay_data = json.loads(overlay_combined)
                if "overlay_path" in overlay_data:
                    result["image_path"] = image_path
                    result["mask_path"] = overlay_data.get("display_mask_path", result["output_path"])
                    result["output_path"] = overlay_data["overlay_path"]
            except asyncio.TimeoutError:
                print("[task_runner] Overlay generation timed out (>60s) — returning masks only")
            except Exception as overlay_err:
                print(f"[task_runner] Overlay generation failed (non-fatal): {overlay_err}")

        return result


# ── Handler registry ──────────────────────────────────────────────────────────

_HANDLERS: Dict[str, Callable] = {
    "inference": _handle_inference,
    "cellpose": _handle_cellpose,
    "report": _handle_report,
}
