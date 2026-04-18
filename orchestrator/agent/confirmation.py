import json
from typing import Dict, Optional

from .constants import LLM_BACKEND
from .builtin_tools import (
    handle_list_tasks,
    handle_queue_task,
    handle_inference_as_task,
    save_radlex_report,
)


class ConfirmationMixin:
    """Handles tool confirmation flow: confirm, deny, and pending state."""

    async def confirm_tool_execution(self, session_id: str = None) -> Optional[Dict]:
        """Execute the pending tool after user confirmation."""
        if not self.pending_tool_call:
            return {"error": "No pending tool call to confirm"}

        pending = self.pending_tool_call
        self.pending_tool_call = None

        tool_name = pending["tool_name"]
        arguments = pending["arguments"]
        print(f"Confirmed - Executing: {tool_name}")

        self.logger.info("\nTOOL CONFIRMATION APPROVED:")
        self.logger.info(f"  Tool: {tool_name}")
        self.logger.info("  User confirmed execution")
        self.logger.info("\nTOOL CALL REQUESTED:")
        self.logger.info(f"  Tool: {tool_name}")
        self.logger.info(f"  Arguments: {json.dumps(arguments, indent=4)}")

        result = await self.tool_registry.execute_tool(tool_name, arguments, logs=True)

        self.logger.info("\nTOOL RESULT:")
        self.logger.info(f"  Tool: {tool_name}")
        result_full = json.dumps(result, indent=4) if isinstance(result, dict) else str(result)
        self.logger.info(f"  Result: {result_full}")

        # Check if result contains an error
        is_error = False
        if isinstance(result, dict):
            is_error = result.get("is_error") or result.get("error")

        execution_history = pending["execution_history"]
        is_gemini = LLM_BACKEND.lower() != "ollama"
        is_stateless = is_gemini and getattr(self.llm_client, "is_stateless_mode", False)

        if result and not is_error:
            result_summary = self._create_result_summary(tool_name, result)
            execution_history.append({
                "tool": tool_name,
                "success": True,
                "result_summary": result_summary,
                "result": result,
            })
            key_data = self._extract_key_data(tool_name, result)
            self._record_and_persist(tool_name, result_summary, key_data, session_id)
            # STM: symmetric update for confirmed tools
            if is_stateless and hasattr(self, "stm_manager"):
                self.stm_manager.update_after_tool(tool_name, result, success=True, summary=result_summary)
            print(f"Tool succeeded: {result_summary}")

            self.logger.info("  Status: SUCCESS")
            self.logger.info(f"  Summary: {result_summary}")

            save_radlex_report(session_id, tool_name, result, arguments)

            confirmed_result = result
        else:
            error_msg = result.get("error") if result else "No result"
            execution_history.append({
                "tool": tool_name,
                "success": False,
                "error": error_msg,
            })
            print(f"Tool failed: {error_msg}")

            self.logger.error("  Status: FAILED")
            self.logger.error(f"  Error: {error_msg}")

            confirmed_result = {"error": str(error_msg) if error_msg else "Tool execution failed", "is_error": True}

        # Build accumulated results for this turn
        turn_accumulated_results = list(pending.get("turn_accumulated_results", [])) + [(tool_name, confirmed_result)]
        turn_remaining_calls = list(pending.get("turn_remaining_calls", []))
        pending_user_id = pending.get("user_id")

        # Drain any built-in tools at the front of the remaining calls
        turn_accumulated_results, turn_remaining_calls = self._drain_builtin_calls(
            turn_remaining_calls, turn_accumulated_results, execution_history, session_id, pending_user_id
        )

        # If there are still remaining MCP calls that need confirmation, chain to next one
        if turn_remaining_calls:
            next_name, next_args = turn_remaining_calls.pop(0)
            self.logger.info("\nCHAINED CONFIRMATION REQUIRED:")
            self.logger.info(f"  Tool: {next_name}")
            self.logger.info(f"  Arguments: {json.dumps(next_args, indent=4)}")
            self.pending_tool_call = {
                "tool_name": next_name,
                "arguments": next_args,
                "goal": pending["goal"],
                "execution_history": execution_history,
                "fileList": pending["fileList"],
                "data": pending["data"],
                "metadata": pending["metadata"],
                "iterations_used": pending["iterations_used"],
                "max_iterations": pending["max_iterations"],
                "session_id": pending.get("session_id"),
                "user_id": pending.get("user_id"),
                "turn_accumulated_results": turn_accumulated_results,
                "turn_remaining_calls": turn_remaining_calls,
            }
            return {
                "type": "confirmation_required",
                "tool_name": next_name,
                "arguments": next_args,
                "message": f"About to execute: {next_name}",
                "execution_history": execution_history,
            }

        # All calls in the turn are resolved — send accumulated results to LLM
        # Stateless mode: skip — next execute_task iteration calls generate_content fresh
        llm_response = None
        if is_gemini and turn_accumulated_results and not is_stateless:
            self.logger.info(f"\nSENDING {len(turn_accumulated_results)} RESULT(S) TO LLM after confirmation")
            try:
                llm_response = await self._send_turn_results_to_llm(turn_accumulated_results)
                self.logger.info("Captured LLM response from function_response(s) (Gemini)")
            except Exception as llm_err:
                print(f"LLM API error after tool execution: {type(llm_err).__name__}: {llm_err}")
                return {"error": f"Tool executed but LLM API unreachable: {llm_err}", "is_error": True}

        # Continue the task from where we left off
        return await self.execute_task(
            goal=pending["goal"],
            data=pending["data"],
            fileList=pending["fileList"],
            max_iterations=pending["max_iterations"] - pending["iterations_used"],
            metadata=pending["metadata"],
            session_id=pending.get("session_id"),
            user_id=pending.get("user_id"),
            _resume_history=execution_history,
            _resume_response=llm_response if is_gemini else None,
        )

    def _drain_builtin_calls(self, remaining_calls, accumulated_results, execution_history, session_id, user_id=None):
        """Process any built-in tools at the front of the remaining calls immediately.

        Returns updated (accumulated_results, remaining_calls).
        """
        while remaining_calls:
            next_name, next_args = remaining_calls[0]

            if next_name == "list_tasks":
                remaining_calls.pop(0)
                result, result_summary = handle_list_tasks(session_id, user_id)

            elif next_name == "queue_task":
                remaining_calls.pop(0)
                result, result_summary = handle_queue_task(session_id, next_args)

            elif next_name == "monai.run_inference":
                remaining_calls.pop(0)
                result, result_summary = handle_inference_as_task(
                    session_id, next_args, self.session_context.entries, set()
                )
            elif next_name == "update_agent_notes":
                if not (LLM_BACKEND.lower() != "ollama" and getattr(self.llm_client, "is_stateless_mode", False)):
                    break
                remaining_calls.pop(0)
                key = next_args.get("key", "")
                value = next_args.get("value", "")
                if hasattr(self, "stm_manager"):
                    self.stm_manager.update_agent_notes(key, value)
                result = {"status": "ok", "key": key}
                result_summary = f"Noted: {key} = {str(value)[:50]}"

            elif next_name == "set_next_objective":
                if not (LLM_BACKEND.lower() != "ollama" and getattr(self.llm_client, "is_stateless_mode", False)):
                    break
                remaining_calls.pop(0)
                objective = next_args.get("objective", "")
                if hasattr(self, "stm_manager"):
                    self.stm_manager.set_next_objective(objective)
                result = {"status": "ok", "objective": objective}
                result_summary = f"Objective set: {objective[:80]}"

            else:
                # Not a built-in tool — stop draining; this needs confirmation
                break

            execution_history.append({
                "tool": next_name,
                "success": True,
                "result_summary": result_summary,
                "result": result,
            })
            accumulated_results.append((next_name, result))

        return accumulated_results, remaining_calls

    def deny_tool_execution(self) -> Dict:
        """Cancel the pending tool call."""
        if not self.pending_tool_call:
            return {"error": "No pending tool call to deny"}

        tool_name = self.pending_tool_call["tool_name"]
        self.pending_tool_call = None
        print(f"Denied - Tool not executed: {tool_name}")

        return {
            "type": "agent_response",
            "answer": f"Tool '{tool_name}' was not executed. How would you like to proceed?",
            "tools_used": [],
            "success": False,
        }

    def get_pending_tool(self) -> Optional[Dict]:
        """Get the pending tool call details."""
        return self.pending_tool_call
