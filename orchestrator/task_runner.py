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
    import tempfile
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

    # Use a real temp file for stderr so the subprocess gets a valid fd
    stderr_file = tempfile.TemporaryFile(mode="w+", encoding="utf-8")

    try:
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(params, errlog=stderr_file))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            mcp_result = await session.call_tool(
                "run_inference",
                arguments={"image_path": image_path, "model_name": model_name},
            )
    except Exception as exc:
        stderr_file.seek(0)
        stderr_output = stderr_file.read().strip()
        if stderr_output:
            print(f"[monai stderr] {stderr_output[-2000:]}")
            raise RuntimeError(f"{exc}\n\nMONAI server output:\n{stderr_output[-1000:]}") from exc
        raise
    finally:
        stderr_file.close()

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
        command=os.path.expandvars(radlex_cfg["command"]),
        args=[os.path.expandvars(a) for a in radlex_cfg.get("args", [])],
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


def _find_mcp_subprocess(cmdline_pattern: str):
    """
    Return the psutil.Process whose command line contains `cmdline_pattern`, or None.
    Used to locate a running MCP stdio server subprocess for watchdog monitoring.
    """
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                if any(cmdline_pattern in arg for arg in cmdline):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    return None


async def _mcp_subprocess_watchdog(
    proc,
    warmup_secs: float = 60,
    idle_check_interval: float = 5,
    max_idle_checks: int = 10,
) -> None:
    """
    General watchdog for any MCP stdio subprocess.

    After `warmup_secs` (to allow model loading / startup), CPU% is sampled every
    `idle_check_interval` seconds. If the process stays below 0.5% CPU for
    `max_idle_checks` consecutive samples it is considered deadlocked and
    RuntimeError is raised.

    This catches any hang where the subprocess is alive but the MCP pipe has
    stalled — OpenMP deadlocks, GPU stalls, infinite waits, etc.

    Pair with asyncio.wait(..., return_when=FIRST_COMPLETED) alongside the actual
    MCP tool call so the caller can cancel the tool call and fail the task.
    """
    import psutil

    await asyncio.sleep(warmup_secs)

    idle_checks = 0
    loop = asyncio.get_event_loop()

    while True:
        try:
            cpu = await loop.run_in_executor(None, proc.cpu_percent, 0.5)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            raise RuntimeError("MCP subprocess exited unexpectedly during tool call.")

        if cpu < 0.5:
            idle_checks += 1
        else:
            idle_checks = 0

        if idle_checks >= max_idle_checks:
            raise RuntimeError(
                f"MCP subprocess appears hung (CPU idle for "
                f"~{int(idle_checks * idle_check_interval)}s after warmup). Task failed."
            )

        await asyncio.sleep(idle_check_interval - 0.5)  # 0.5s already spent in cpu_percent


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

        # Locate the cellpose subprocess for hang detection (CPU idle watchdog)
        cellpose_proc = _find_mcp_subprocess("mcp-cellpose/server.py")
        if cellpose_proc is None:
            print("[task_runner] Warning: could not locate cellpose subprocess; hang detection disabled")

        infer_task = asyncio.create_task(
            session.call_tool("segment_cells_2d", arguments=arguments)
        )

        tasks_to_wait = [infer_task]
        if cellpose_proc is not None:
            watch_task = asyncio.create_task(_mcp_subprocess_watchdog(cellpose_proc))
            tasks_to_wait.append(watch_task)

        done, pending = await asyncio.wait(tasks_to_wait, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

        if cellpose_proc is not None and watch_task in done and not infer_task.done():
            exc = watch_task.exception()
            raise exc if exc else RuntimeError("Cellpose process hung during inference")
        mcp_result = infer_task.result()

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
