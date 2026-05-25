from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
from datetime import datetime

import task_runner
import database as db


# ---------- Built-in tool schemas (registered alongside MCP tools) ----------

BUILTIN_TOOLS: Dict[str, Dict] = {
    "queue_task": {
        "description": (
            "Queue a long-running operation as a background task. "
            "Use this instead of calling a tool directly whenever the operation may take more than a few seconds "
            "(e.g. MONAI inference, report generation, bulk analysis). "
            "The function returns immediately so you can keep talking to the user. "
            "The user will receive a notification when the task finishes."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "task_type": {
                    "type": "string",
                    "description": "Category of the task. Use 'inference' for MONAI model runs, 'cellpose' for Cellpose cell segmentation, 'report' for report generation, or any descriptive string for other tasks.",
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable label shown in the Results tab, e.g. 'WholeBody segmentation on PANCREAS_0001'.",
                },
                "input_data": {
                    "type": "object",
                    "description": "Task-specific inputs as a JSON object. For 'inference': {image_path, model_name}. For 'cellpose': {image_path} - one file per task, call once per file. For 'report': {task_ids, patient_context}.",
                },
            },
            "required": ["task_type", "description", "input_data"],
        },
        "server": "__builtin__",
        "original_name": "queue_task",
        "transport": "builtin",
    },
    "list_tasks": {
        "description": (
            "List all background tasks for the current session and their status. "
            "Use this when the user asks whether their inference or report tasks have finished, "
            "or to check how many tasks are still running."
        ),
        "schema": {
            "type": "object",
            "properties": {},
        },
        "server": "__builtin__",
        "original_name": "list_tasks",
        "transport": "builtin",
    },
    "goal_achieved": {
        "description": (
            "Call this tool when you have completed the user's goal or answered their question. "
            "You MUST call this tool to signal completion — do not just say 'done' in text."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Final answer or summary of what was accomplished.",
                },
            },
            "required": ["summary"],
        },
        "server": "__builtin__",
        "original_name": "goal_achieved",
        "transport": "builtin",
    },
    "need_more_info": {
        "description": (
            "Call this tool when you cannot proceed without additional information from the user."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "What specific information is needed from the user.",
                },
            },
            "required": ["question"],
        },
        "server": "__builtin__",
        "original_name": "need_more_info",
        "transport": "builtin",
    },
}


# ---------- Shared handler functions (used by both execute_task and confirm_tool_execution) ----------

def handle_list_tasks(session_id: Optional[str], user_id: Optional[str] = None) -> Tuple[Dict, str]:
    """Execute the list_tasks built-in and return (result, summary)."""
    tasks = db.list_tasks(user_id=user_id) if user_id else db.list_tasks(session_id=session_id)
    summary_list = []
    for t in tasks:
        entry = {
            "id": t["id"],
            "type": t["task_type"],
            "description": t["description"],
            "status": t["status"],
            "error": t.get("error"),
        }
        if t["status"] == "done" and t.get("result"):
            r = t["result"]
            if isinstance(r, dict):
                entry["result"] = {k: v for k, v in r.items()
                                   if k not in ("output_path", "mask_path", "image_path", "overlay_path")}
        summary_list.append(entry)
    result = {
        "tasks": summary_list,
        "running": sum(1 for t in tasks if t["status"] in ("queued", "running")),
        "done": sum(1 for t in tasks if t["status"] == "done"),
        "failed": sum(1 for t in tasks if t["status"] == "failed"),
    }
    result_summary = f"Tasks: {result['running']} running, {result['done']} done, {result['failed']} failed"
    return result, result_summary


def handle_queue_task(session_id: Optional[str], arguments: Dict) -> Tuple[Dict, str]:
    """Execute the queue_task built-in and return (result, summary)."""
    task_type = arguments.get("task_type", "generic")
    description = arguments.get("description", "Background task")
    input_data = arguments.get("input_data", {})
    task_id = task_runner.submit_task(
        session_id=session_id or "unknown",
        task_type=task_type,
        description=description,
        input_data=input_data,
    )
    result = {
        "task_id": task_id,
        "status": "queued",
        "message": f"Task queued: '{description}'. You'll receive a notification when it finishes.",
    }
    result_summary = f"Queued background task: {description}"
    return result, result_summary


def handle_inference_as_task(
    session_id: Optional[str],
    arguments: Dict,
    session_context_entries: List[Dict],
    inference_queued: set,
) -> Tuple[Dict, str]:
    """Queue monai.run_inference as a background task and return (result, summary).

    Also updates *inference_queued* in-place so callers can track what was already queued.
    """
    image_path = arguments.get("image_path", "")
    model_name = arguments.get("model_name", "")

    # Pull body_part / modality from session context (set by analyze_image)
    body_part = next(
        (e["data"].get("body_part", "") for e in reversed(session_context_entries)
         if e.get("data", {}).get("body_part")),
        "",
    )
    modality = next(
        (e["data"].get("modality", "") for e in reversed(session_context_entries)
         if e.get("data", {}).get("modality")),
        "",
    )

    queued_tasks: List[Dict] = []
    if image_path and image_path not in inference_queued:
        inf_fname = Path(image_path).name
        inf_desc = f"Inference: {inf_fname}" + (f" ({model_name})" if model_name else "")
        inf_task_id = task_runner.submit_task(
            session_id=session_id or "unknown",
            task_type="inference",
            description=inf_desc,
            input_data={
                "image_path": image_path,
                "model_name": model_name,
                "body_part": body_part,
                "modality": modality,
            },
        )
        inference_queued.add(image_path)
        queued_tasks.append({"task_id": inf_task_id, "file": inf_fname})

    result = {
        "tasks_queued": len(queued_tasks),
        "tasks": queued_tasks,
        "message": f"Queued inference for {len(queued_tasks)} file(s) using {model_name}. Results will appear in the Results tab.",
    }
    result_summary = f"Queued {len(queued_tasks)} inference task(s)"
    return result, result_summary


def save_markdown_report(session_id: Optional[str], tool_name: str, arguments: Dict) -> None:
    """Persist a utils.write_file result to the DB so it appears in the Results tab."""
    if not session_id or tool_name != "utils.write_file":
        return
    path = arguments.get("path", "")
    content = arguments.get("content", "")
    filename = Path(path).name if path else "report"
    tid = db.create_task(session_id, "markdown_report", f"Report: {filename}", {"path": path})
    db.update_task(tid, "done", result={"file_path": path, "filename": filename, "content": content})
    print(f"[agent] Saved markdown report '{filename}' to DB as task {tid[:8]}")


def save_radlex_report(session_id: Optional[str], tool_name: str, result: Any, arguments: Dict) -> None:
    """Persist a radlex report to the DB so it appears in the Report tab."""
    if not session_id or tool_name != "radlex.generate_radiology_report":
        return
    report_wrap = {
        "patient_context": {},
        "findings": [],
        "radlex_template": result,
        "narrative": {},
        "generated_at": datetime.now().isoformat(),
    }
    rtid = db.create_task(session_id, "report", "Radlex Template Report", arguments)
    db.update_task(rtid, "done", result=report_wrap)
    print(f"[agent] Saved radlex report to DB as task {rtid[:8]}")
