import asyncio
import os
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

import database as db

from .constants import LLM_BACKEND
from .prompts import FIRST_ITERATION_PROMPT_TEMPLATE, EVAL_PROMPT_TEMPLATE, EVAL_PROMPT_TEMPLATE_STM
from .builtin_tools import (
    handle_list_tasks,
    handle_queue_task,
    handle_inference_as_task,
    save_radlex_report,
    save_markdown_report,
)


class ExecutionMixin:
    """Core agentic execution loop — execute_task and its sub-methods."""

    async def execute_task(
        self,
        goal: str,
        data: Any = None,
        fileList: Any = None,
        max_iterations: int = 10,
        metadata: Dict = None,
        _resume_history: List = None,
        _resume_response: Optional[Any] = None,
        session_id: str = None,
        user_id: str = None,
    ) -> Optional[Dict]:
        """
        Truly autonomous task execution - agent reasons about tools and executes.

        Args:
            goal: Natural language description of what to accomplish
            data: Optional data context (e.g., patient data to save)
            fileList: Optional list of images for processing
            max_iterations: Maximum number of tool executions allowed
            metadata: Optional dict with modality, body_part for filtering models
            _resume_history: Optional execution history to resume from
            _resume_response: Optional LLM response to use instead of generating new one
            session_id: Session identifier for DB persistence

        Returns:
            Final result if successful, None if goal not achieved
        """
        if session_id:
            self.logger.start_session(session_id)

        async with self._execution_lock:
            return await self._execute_task_inner(
                goal, data, fileList, max_iterations, metadata,
                _resume_history, _resume_response, session_id, user_id,
            )

    async def _execute_task_inner(
        self,
        goal: str,
        data: Any = None,
        fileList: Any = None,
        max_iterations: int = 10,
        metadata: Dict = None,
        _resume_history: List = None,
        _resume_response: Optional[Any] = None,
        session_id: str = None,
        user_id: str = None,
    ) -> Optional[Dict]:
        print(f"\n{'='*80}")
        print("Autonomous agent: ", self.is_agent_autonomous)
        print(f"Starting autonomous task: {goal}")
        self.logger.info("=" * 80)
        self.logger.info(f"TASK START: {goal}")
        self.logger.info(f"Max iterations: {max_iterations}")
        if metadata:
            self.logger.info(f"Metadata: {json.dumps(metadata, indent=2)}")
            print(f"Metadata: modality={metadata.get('modality')}, body_part={metadata.get('body_part')}")
        if fileList:
            self.logger.info(f"Files provided: {len(fileList)} file(s)")
        if data:
            self.logger.info(f"Data provided: {len(str(data))} chars")

        execution_history = _resume_history if _resume_history else []
        iterations = 0
        final_result = None
        _inference_queued: set = set()
        is_gemini = LLM_BACKEND.lower() != "ollama"
        is_stateless = is_gemini and getattr(self.llm_client, "is_stateless_mode", False)

        # STM: init state only on first call (not on recursive resume)
        if is_stateless and _resume_history is None and hasattr(self, "stm_manager"):
            image_paths = [fp for fp, _ in fileList] if fileList and isinstance(fileList, list) and fileList and isinstance(fileList[0], tuple) else []
            self.stm_manager.init_state(goal, data, image_paths)

        while iterations < max_iterations:
            iterations += 1
            print(f"Iteration {iterations}/{max_iterations}")
            # STM: expire outdated skill references
            if is_stateless and hasattr(self, "stm_manager"):
                self.stm_manager.tick_skill_ttls()
            try:
                # Build prompt and get LLM response
                if is_gemini and _resume_response is not None:
                    response = _resume_response
                    _resume_response = None

                    self.logger.info(f"\n{'='*60}")
                    self.logger.info(f"ITERATION {iterations}/{max_iterations}")
                    self.logger.info(f"{'='*60}")
                    self.logger.info("\nUSING RESPONSE FROM send_function_response (no redundant prompt)\n")
                    self.logger.info(f"\nLLM RAW RESPONSE:\n{response}\n")

                    print("Using response from send_function_response (Gemini optimization)")
                else:
                    prompt, images_for_llm = self._build_prompt(
                        goal, data, fileList, execution_history, is_gemini
                    )
                    print(f"Prompt: {prompt}")

                    self.logger.info(f"\n{'='*60}")
                    self.logger.info(f"ITERATION {iterations}/{max_iterations}")
                    self.logger.info(f"{'='*60}")
                    self.logger.info(f"\nPROMPT SENT TO LLM:\n{prompt}\n")
                    if images_for_llm:
                        self.logger.info(f"Images attached: {len(images_for_llm)} file(s)")

                    composed_prompt = prompt
                    if is_stateless and hasattr(self, "stm_manager"):
                        stm_text = self.stm_manager.render_state_text()
                        if stm_text:
                            composed_prompt = "\n\n---\n\n".join([stm_text, prompt])

                    self.logger.info(f"\nCOMPOSED PROMPT SENT TO LLM:\n{composed_prompt}\n")

                    content_parts = [composed_prompt]
                    loop = asyncio.get_event_loop()
                    try:
                        response = await asyncio.wait_for(
                            loop.run_in_executor(
                                None, self.llm_client.generate_content, content_parts, images_for_llm
                            ),
                            timeout=120,
                        )
                    except asyncio.TimeoutError:
                        self.logger.error("LLM call timed out after 120s")
                        return {
                            "type": "agent_response",
                            "answer": "The AI model took too long to respond. Please try again.",
                            "tools_used": [],
                            "execution_history": execution_history,
                            "success": False,
                        }
                    self.logger.info(f"\nLLM RAW RESPONSE:\n{response}\n")

                # Parse the LLM response
                has_text, has_function_call, turn_calls, text_content = self._parse_llm_response(response)

                # Handle text-only responses (goal achieved / need more info fallbacks)
                text_result = self._handle_text_signals(
                    has_text, has_function_call, text_content, response, execution_history, final_result
                )
                if text_result is not None:
                    return text_result

                # Process each function call in the turn
                turn_results, should_return = await self._process_tool_calls(
                    turn_calls, execution_history, session_id, _inference_queued,
                    goal, data, fileList, max_iterations, metadata, iterations, user_id,
                )
                if should_return is not None:
                    return should_return

                # Update final_result from last successful tool
                for _tn, _tr in turn_results:
                    if isinstance(_tr, dict) and not _tr.get("is_error"):
                        final_result = _tr

                # Stateful only: send tool results in the same chat turn.
                # Stateless mode rebuilds a fresh prompt on next loop iteration.
                if is_gemini and turn_results and not is_stateless:
                    _resume_response = await self._send_turn_results_to_llm(turn_results)

                # If agent responded with text but no tool call (and not caught above)
                if has_text and not has_function_call and text_content:
                    text_response = text_content.strip()
                    if len(text_response) > 20:
                        last_failed = execution_history and not execution_history[-1].get('success')
                        if last_failed:
                            print("Agent explaining tool error to user")
                        else:
                            print("Agent responded with text (no tools needed for this query)")
                        tools_used = [event['tool'] for event in execution_history if event.get('success')]
                        return {
                            "type": "agent_response",
                            "answer": text_response,
                            "tools_used": tools_used,
                            "execution_history": execution_history,
                            "success": not last_failed,
                        }
                    else:
                        print("Agent response too short, continuing...")
                        execution_history.append({
                            "tool": "none",
                            "success": False,
                            "error": "Agent response was not actionable",
                        })

            except Exception as e:
                print(f"Error in agentic workflow: {type(e).__name__}: {e}")
                self.logger.error(f"Exception in workflow: {type(e).__name__}: {e}")
                error_message = str(e) if e else "Unknown workflow error"

                if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message or "quota" in error_message.lower():
                    print(f"Rate limit hit - stopping: {error_message}")
                    return {
                        "type": "agent_response",
                        "answer": "API rate limit reached. Please wait a few minutes before trying again, or check your API quota.",
                        "tools_used": [],
                        "execution_history": execution_history,
                        "success": False,
                    }

                execution_history.append({
                    "tool": "workflow",
                    "success": False,
                    "error": error_message,
                    "result": None,
                })

        print("Max iterations reached or goal not achieved.")
        self.logger.warning(f"TASK ENDED: Max iterations reached ({max_iterations}) - goal not achieved")
        self.logger.info(f"Total successful tools: {sum(1 for e in execution_history if e.get('success'))}")
        self.logger.info(f"={'='*80}\n")
        return None

    # ---------- Sub-methods ----------

    def _build_prompt(self, goal, data, fileList, execution_history, is_gemini):
        """Build the prompt string and extract images for the LLM.

        Returns (prompt_str, images_for_llm_or_None).
        """
        data_context = ""
        if data:
            data_context = f"\n\nDATA AVAILABLE:\n{json.dumps(data, indent=2)}"

        image_context = ""
        images_for_llm = None

        if fileList and isinstance(fileList, list) and fileList:
            file_paths = []
            dicom_dir_paths = []

            _DICOM_EXTS = {'.dcm', '.ima', '.img'}

            for temp_filepath, _ in fileList:
                if os.path.isdir(temp_filepath):
                    # Check for explicit DICOM extensions — if found, treat as a DICOM series.
                    # Otherwise expand the directory contents as individual files.
                    try:
                        entries = sorted(f for f in os.listdir(temp_filepath) if not f.startswith('.'))
                        exts = {os.path.splitext(f)[1].lower() for f in entries}
                        if exts & _DICOM_EXTS:
                            dicom_dir_paths.append(temp_filepath)
                        else:
                            for entry in entries:
                                file_paths.append(os.path.join(temp_filepath, entry))
                    except OSError:
                        dicom_dir_paths.append(temp_filepath)
                else:
                    file_paths.append(temp_filepath)

            parts = []
            if file_paths:
                parts.append("Files: " + ", ".join(file_paths))
            if dicom_dir_paths:
                parts.append(
                    "DICOM series directories (treat each as a single 3D volume): "
                    + ", ".join(f"[DICOM SERIES DIR] {p}" for p in dicom_dir_paths)
                )
            image_context = "\n\nFILES AVAILABLE: Yes\n" + "\n".join(parts)

            # Do not send image data to the LLM - file paths in the prompt are sufficient
            # for the agent to call the right tools. Sending large images to flash-lite
            # models causes timeouts and is not needed for tool dispatch decisions.
            # images_for_llm = []
            # for temp_filepath, content in fileList:
            #     if os.path.isdir(temp_filepath):
            #         continue
            #     ext = temp_filepath.lower()
            #     if not ext.endswith(('.nii', '.nii.gz', '.dcm', '.mha', '.mhd', '.nrrd')):
            #         if len(content) < 5 * 1024 * 1024:
            #             images_for_llm.append((temp_filepath, content))
            # if not images_for_llm:
            #     images_for_llm = None
            images_for_llm = None
        elif fileList:
            image_context = "\n\nFILES AVAILABLE:\nImage data provided"

        session_ctx = self.session_context.build_context_string()
        session_block = f"\n\n{session_ctx}" if session_ctx else ""

        if not execution_history:
            prompt = FIRST_ITERATION_PROMPT_TEMPLATE.format(
                goal=goal,
                data_context=data_context,
                image_context=image_context,
                session_block=session_block,
            )
        else:
            history_text = ""
            if not is_gemini and execution_history:
                history_text = "\n\nExecution history:\n"
                for i, event in enumerate(execution_history, 1):
                    history_text += f"{i}. Called {event['tool']} → "
                    if event['success']:
                        result_summary = event.get('result_summary', 'Success')
                        result_data = event.get('result', {})
                        history_text += f"Success. Result: {result_summary}\n"
                        if result_data:
                            result_str = json.dumps(result_data, indent=2)
                            if len(result_str) > 500:
                                history_text += f"   Response data (truncated): {result_str[:500]}...\n"
                            else:
                                history_text += f"   Response data: {result_str}\n"
                    else:
                        error_msg = event.get('error') or 'Unknown error'
                        if error_msg is None or (isinstance(error_msg, str) and not error_msg.strip()):
                            error_msg = 'Tool execution failed'
                        history_text += f"Failed: {error_msg}\n"

            # Include compact context for the most recent two calls in stateless mode.
            if is_gemini and getattr(self.llm_client, "is_stateless_mode", False) and execution_history:
                recent_events = execution_history[-2:]
                recent_text = "\n\nRecent tool results (last 2):\n"
                start_index = max(1, len(execution_history) - len(recent_events) + 1)
                for idx, event in enumerate(recent_events, start=start_index):
                    tool_name = event.get('tool', 'unknown_tool')
                    if event.get('success'):
                        result_summary = event.get('result_summary') or 'Success'
                        recent_text += f"{idx}. {tool_name} -> Success. Summary: {result_summary}\n"
                        result_data = event.get('result')
                        if result_data:
                            result_str = json.dumps(result_data, default=str)
                            if len(result_str) > 400:
                                result_str = result_str[:400] + "..."
                            recent_text += f"   Data: {result_str}\n"
                    else:
                        error_msg = event.get('error') or 'Tool execution failed'
                        if error_msg is None or (isinstance(error_msg, str) and not error_msg.strip()):
                            error_msg = 'Tool execution failed'
                        recent_text += f"{idx}. {tool_name} -> Failed: {error_msg}\n"

                history_text += recent_text

            eval_template = EVAL_PROMPT_TEMPLATE_STM if (is_gemini and getattr(self.llm_client, "is_stateless_mode", False)) else EVAL_PROMPT_TEMPLATE
            prompt = eval_template.format(history_text=history_text)

        return prompt, images_for_llm

    def _parse_llm_response(self, response):
        """Scan LLM response parts for text and function calls.

        Returns (has_text, has_function_call, turn_calls, full_text_content).
        """
        has_text = False
        has_function_call = False
        turn_calls = []
        full_text = ""

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    has_text = True
                    full_text = part.text

                if hasattr(part, 'function_call') and part.function_call:
                    has_function_call = True
                    raw_name = part.function_call.name
                    raw_args = dict(part.function_call.args)
                    # Resolve tool name if missing prefix
                    if raw_name not in self.available_tools:
                        for full_name in self.available_tools.keys():
                            if full_name.endswith(f".{raw_name}"):
                                print(f"Resolved tool name: {raw_name} -> {full_name}")
                                raw_name = full_name
                                break
                    turn_calls.append((raw_name, raw_args))

        return has_text, has_function_call, turn_calls, full_text

    def _handle_text_signals(self, has_text, has_function_call, text_content, response, execution_history, final_result):
        """Check for GOAL_ACHIEVED or NEED_MORE_INFO text fallbacks.

        Returns a result dict if we should return early, or None to continue.
        """
        if not has_text or has_function_call or not text_content:
            return None

        text_upper = text_content.strip().upper()

        if "GOAL_ACHIEVED" in text_upper or "GOAL ACHIEVED" in text_upper:
            self.logger.warning("LLM used text GOAL_ACHIEVED instead of goal_achieved tool — falling back to string detection")
            print("Agent declares: Goal achieved! (text fallback)")
            answer = self._extract_answer_from_results(text_content, execution_history, final_result)
            tools_used = [event['tool'] for event in execution_history if event['success']]

            self.logger.info(f"\n{'='*60}")
            self.logger.info("TASK COMPLETED SUCCESSFULLY")
            self.logger.info(f"  Iterations used: {len(execution_history)}")
            self.logger.info(f"  Tools used: {tools_used}")
            self.logger.info(f"  Answer: {answer}")
            self.logger.info(f"{'='*80}\n")

            return {
                "type": "agent_response",
                "answer": answer,
                "tools_used": tools_used,
                "execution_history": execution_history,
                "success": True,
            }

        if "NEED MORE INFO" in text_upper:
            self.logger.warning("LLM used text NEED MORE INFO instead of need_more_info tool — falling back to string detection")
            print("Agent requests more information to proceed. (text fallback)")
            return {
                "type": "agent_response",
                "answer": text_content.strip(),
                "tools_used": [],
                "execution_history": execution_history,
                "success": False,
            }

        return None

    async def _process_tool_calls(
        self, turn_calls, execution_history, session_id, inference_queued,
        goal, data, fileList, max_iterations, metadata, iterations, user_id=None,
    ):
        """Process each function call in the turn.

        Returns (turn_results, should_return).
        should_return is None to continue the loop, or a dict to return from execute_task.
        """
        turn_results = []

        for tool_name, arguments in turn_calls:

            # Block repeated failures
            if len(execution_history) >= 2:
                last_event = execution_history[-1]
                prev_event = execution_history[-2]
                if (
                    last_event.get('tool') == tool_name and not last_event.get('success')
                    and prev_event.get('tool') == tool_name and not prev_event.get('success')
                ):
                    print(f"Agent tried to repeat tool '{tool_name}' after 2 consecutive failures - skipping")
                    error_msg = f"Repetition prevented: Tool '{tool_name}' failed twice consecutively. Try a different tool."
                    execution_history.append({"tool": tool_name, "success": False, "error": error_msg})
                    turn_results.append((tool_name, {"error": error_msg, "is_error": True}))
                    continue

            # --- Built-in tool intercepts ---
            if tool_name == "list_tasks":
                result, result_summary = handle_list_tasks(session_id, user_id)
                execution_history.append({"tool": tool_name, "success": True, "result_summary": result_summary, "result": result})
                turn_results.append((tool_name, result))
                continue

            if tool_name == "queue_task":
                result, result_summary = handle_queue_task(session_id, arguments)
                execution_history.append({"tool": tool_name, "success": True, "result_summary": result_summary, "result": result})
                # Return immediately — task is queued, no further LLM iterations needed
                return turn_results, {
                    "type": "agent_response",
                    "answer": result.get("message", "Task has been queued and will run in the background."),
                    "tools_used": ["queue_task"],
                    "execution_history": execution_history,
                    "success": True,
                }

            if tool_name == "goal_achieved":
                summary = arguments.get("summary", "")
                answer = summary if summary else self._extract_answer_from_results("", execution_history, None)
                tools_used = [event['tool'] for event in execution_history if event.get('success')]

                self.logger.info(f"\n{'='*60}")
                self.logger.info("TASK COMPLETED VIA goal_achieved TOOL")
                self.logger.info(f"  Iterations used: {iterations}")
                self.logger.info(f"  Tools used: {tools_used}")
                self.logger.info(f"  Answer: {answer}")
                self.logger.info(f"{'='*60}\n")

                return turn_results, {
                    "type": "agent_response",
                    "answer": answer,
                    "tools_used": tools_used,
                    "execution_history": execution_history,
                    "success": True,
                }

            if tool_name == "need_more_info":
                question = arguments.get("question", "I need more information to proceed.")
                return turn_results, {
                    "type": "agent_response",
                    "answer": question,
                    "tools_used": [],
                    "execution_history": execution_history,
                    "success": False,
                }

            # --- STM built-in handlers ---
            if tool_name == "update_agent_notes":
                if not (LLM_BACKEND.lower() != "ollama" and getattr(self.llm_client, "is_stateless_mode", False)):
                    turn_results.append((tool_name, {"error": "Tool unavailable in stateful mode", "is_error": True}))
                    continue
                key = arguments.get("key", "")
                value = arguments.get("value", "")
                if hasattr(self, "stm_manager"):
                    self.stm_manager.update_agent_notes(key, value)
                result = {"status": "ok", "key": key}
                result_summary = f"Noted: {key} = {str(value)[:50]}"
                self.logger.info(f"\nSTM update_agent_notes: [{key}] = {value}")
                execution_history.append({"tool": tool_name, "success": True, "result_summary": result_summary, "result": result})
                turn_results.append((tool_name, result))
                continue

            if tool_name == "set_next_objective":
                if not (LLM_BACKEND.lower() != "ollama" and getattr(self.llm_client, "is_stateless_mode", False)):
                    turn_results.append((tool_name, {"error": "Tool unavailable in stateful mode", "is_error": True}))
                    continue
                objective = arguments.get("objective", "")
                if hasattr(self, "stm_manager"):
                    self.stm_manager.set_next_objective(objective)
                result = {"status": "ok", "objective": objective}
                result_summary = f"Objective set: {objective[:80]}"
                self.logger.info(f"\nSTM set_next_objective: {objective}")
                execution_history.append({"tool": tool_name, "success": True, "result_summary": result_summary, "result": result})
                turn_results.append((tool_name, result))
                continue

            # Cellpose segmentation always runs as a background task, never call directly.
            # Calling the MCP tool inline hangs the agent loop on GPU stalls in deployment.
            if tool_name in ("cellpose.segment_cells_2d", "cellpose.segment_cells_3d", "cellpose.segment_cells_batch"):
                image_path = arguments.get("image_path", "")
                fname = Path(image_path).name if image_path else "image"
                result, result_summary = handle_queue_task(session_id, {
                    "task_type": "cellpose",
                    "description": f"Cellpose segmentation: {fname}",
                    "input_data": {**arguments, "model_type": "cpsam"},
                })
                execution_history.append({"tool": tool_name, "success": True, "result_summary": result_summary, "result": result})
                return turn_results, {
                    "type": "agent_response",
                    "answer": result.get("message", "Cellpose segmentation has been queued and will run in the background."),
                    "tools_used": ["queue_task"],
                    "execution_history": execution_history,
                    "success": True,
                }

            # Inference always runs in background (non-autonomous mode)
            if tool_name == "monai.run_inference" and not self.is_agent_autonomous:
                result, result_summary = handle_inference_as_task(
                    session_id, arguments, self.session_context.entries, inference_queued
                )
                execution_history.append({"tool": tool_name, "success": True, "result_summary": result_summary, "result": result})
                turn_results.append((tool_name, result))
                continue

            # Check if confirmation is required
            if self.require_confirmation:
                print(f"Tool confirmation required: {tool_name}")
                self.logger.info("\nTOOL CONFIRMATION REQUIRED:")
                self.logger.info(f"  Tool: {tool_name}")
                self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")

                current_idx = len(turn_results)
                remaining_calls = turn_calls[current_idx + 1:]

                self.pending_tool_call = {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "goal": goal,
                    "execution_history": execution_history,
                    "fileList": fileList,
                    "data": data,
                    "metadata": metadata,
                    "iterations_used": iterations,
                    "max_iterations": max_iterations,
                    "session_id": session_id,
                    "user_id": user_id,
                    "turn_accumulated_results": list(turn_results),
                    "turn_remaining_calls": remaining_calls,
                }
                return turn_results, {
                    "type": "confirmation_required",
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "message": f"About to execute: {tool_name}",
                    "execution_history": execution_history,
                }

            # Execute the MCP tool
            print(f"Executing: {tool_name}")
            self.logger.info("\nTOOL CALL REQUESTED:")
            self.logger.info(f"  Tool: {tool_name}")
            self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")

            result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)

            self.logger.info("\nTOOL RESULT:")
            self.logger.info(f"  Tool: {tool_name}")
            result_full = json.dumps(result, indent=4) if isinstance(result, dict) else str(result)
            self.logger.info(f"  Result: {result_full}")

            is_error = False
            if isinstance(result, dict):
                is_error = result.get("is_error") or result.get("error") or "error" in str(result.get("text", "")).lower()

            print(f"TOOL EXECUTION RESULT: {result}")

            if result and not is_error:
                result_summary = self._create_result_summary(tool_name, result)
                execution_history.append({
                    "tool": tool_name, "success": True,
                    "result_summary": result_summary, "result": result,
                })
                key_data = self._extract_key_data(tool_name, result)
                self._record_and_persist(tool_name, result_summary, key_data, session_id)
                # STM: record completed step and extract artifacts
                if LLM_BACKEND.lower() != "ollama" and getattr(self.llm_client, "is_stateless_mode", False) and hasattr(self, "stm_manager"):
                    self.stm_manager.update_after_tool(tool_name, result, success=True, summary=result_summary)
                print(f"Tool succeeded: {result_summary}")
                self.logger.info("  Status: SUCCESS")
                self.logger.info(f"  Summary: {result_summary}")

                save_radlex_report(session_id, tool_name, result, arguments)
                save_markdown_report(session_id, tool_name, arguments)
                turn_results.append((tool_name, result))

            elif result and is_error:
                error_msg = result.get("error") or result.get("text") or "Unknown error"
                if error_msg is None or (isinstance(error_msg, str) and not error_msg.strip()):
                    error_msg = "Tool execution failed without error details"
                execution_history.append({
                    "tool": tool_name, "success": False,
                    "error": str(error_msg), "result": result,
                })
                # STM: record failed step
                if LLM_BACKEND.lower() != "ollama" and getattr(self.llm_client, "is_stateless_mode", False) and hasattr(self, "stm_manager"):
                    self.stm_manager.update_after_tool(tool_name, result, success=False, summary=str(error_msg)[:200])

                # Persist a failed task record so the Results tab shows it
                _RESULT_TOOLS = {"monai.analyze_image", "monai.run_inference", "monai.download_model"}
                if session_id and tool_name in _RESULT_TOOLS:
                    _path = arguments.get("path") or arguments.get("image_path") or ""
                    _label = {
                        "monai.analyze_image": "Image Analysis",
                        "monai.run_inference": "Inference",
                        "monai.download_model": "Model Download",
                    }.get(tool_name, tool_name)
                    _fname = Path(_path).name if _path else "unknown file"
                    _tid = db.create_task(session_id, "inference", f"{_label}: {_fname}", {"path": _path, **arguments})
                    db.update_task(_tid, "failed", None, str(error_msg))

                print(f"Tool failed: {error_msg}")
                self.logger.error("  Status: FAILED")
                self.logger.error(f"  Error: {error_msg}")
                turn_results.append((tool_name, {"error": str(error_msg), "is_error": True}))

            else:
                execution_history.append({"tool": tool_name, "success": False, "error": "Execution returned no result"})
                print("Tool execution failed")
                self.logger.error("  Status: FAILED - No result returned")
                turn_results.append((tool_name, {"error": "Execution returned no result", "is_error": True}))

        return turn_results, None

    async def _send_turn_results_to_llm(self, turn_results):
        """Send all accumulated results to the LLM in one message. Returns LLM response."""
        # Collect images from tool results that signal image_for_llm
        images = []
        for _name, result in turn_results:
            if isinstance(result, dict) and result.get("image_for_llm") and result.get("path"):
                try:
                    from PIL import Image
                    img = Image.open(result["path"]).convert("RGB")
                    images.append(img)
                    print(f"Injecting tool image into LLM vision context: {result['path']}")
                except Exception as e:
                    print(f"Could not load tool image for LLM: {e}")
        images = images or None

        loop = asyncio.get_event_loop()
        if len(turn_results) > 1:
            self.logger.info(f"\nSENDING {len(turn_results)} RESULTS TO LLM via send_multiple_function_responses")
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: self.llm_client.send_multiple_function_responses(turn_results, images=images)
                ),
                timeout=120,
            )
        else:
            single_name, single_data = turn_results[0]
            self.logger.info("\nSENDING FULL RESULT TO LLM via send_function_response")
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: self.llm_client.send_function_response(single_name, single_data, images=images)
                ),
                timeout=120,
            )
            self.logger.info("Captured response from function_response(s) - will use on next iteration")
            return response
