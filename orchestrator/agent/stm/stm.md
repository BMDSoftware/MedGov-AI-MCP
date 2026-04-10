[STM Documentation]

# STM Usage in the Agent

## Purpose

This document explains how Short-Term Memory (STM) is used in the orchestrator agent, including:

- how STM is enabled/disabled
- what is sent to the LLM
- how tool history is tracked
- how skills history is tracked
- how agent state is represented and updated

## Where STM is Enabled

STM is exposed only when LLM mode is `stateless`.

- LLM mode check in agent initialization: [orchestrator/agent/core.py](../orchestrator/agent/core.py)
- Settings source for this decision: [orchestrator/app_settings.json](../orchestrator/app_settings.json)

Initialization flow:

1. Agent discovers MCP and built-in tools.
2. If `_is_stateless_llm_mode()` is true, STM built-ins are added:
   - `update_agent_notes`
   - `set_next_objective`
3. In `stateful` mode, STM built-ins are not exposed.

## What Is Sent to the LLM

## First prompt in an execution loop

The prompt built for first iteration is based on:

- goal
- optional data context
- optional files context
- session context string

Source:

- prompt construction and composition: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py)
- session context builder: [orchestrator/sessionContext.py](../orchestrator/sessionContext.py)

## STM payload (stateless mode)

In stateless mode, the composed prompt sent to Gemini includes:

1. `stm_manager.render_state_text()` output (`## AGENT STATE` block)
2. separator (`---`)
3. normal task prompt

This makes each stateless request self-contained with current memory/state.

Source:

- composition with STM text: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py)
- state rendering: [orchestrator/agent/stm/manager.py](../orchestrator/agent/stm/manager.py)

## Stateful mode payload

In stateful mode, the agent sends only the normal prompt and uses Gemini chat session memory.
Tool results are sent back with function responses in the same chat turn.

Source:

- chat vs direct generation behavior: [orchestrator/gemini_client.py](../orchestrator/gemini_client.py)
- function response behavior: [orchestrator/gemini_client.py](../orchestrator/gemini_client.py)
- stateful continuation logic: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py)

## Eval Prompt Selection

There are two evaluation prompts:

- `EVAL_PROMPT_TEMPLATE`: generic/non-STM
- `EVAL_PROMPT_TEMPLATE_STM`: STM-aware completion contract

Selection rule:

- stateless mode -> STM eval template
- otherwise -> generic eval template

Source:

- templates: [orchestrator/agent/prompts.py](../orchestrator/agent/prompts.py)
- selection: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py)

## Tool History

Two histories are used with different purposes.

## 1) Execution history (per task loop)

`execution_history` is an in-memory event list for the current execute loop.
Each event stores tool name, success/failure, summary, and optionally error/result.

Used for:

- loop decision context
- duplicate failure prevention
- return payload (`tools_used`, `execution_history`)
- compact recent-results injection in stateless eval path

Source:

- execution loop and event appends: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py)

## 2) Session context history (cross-query within session)

`SessionContext.entries` stores condensed successful tool outcomes.
Each record includes:

- tool
- summary
- key data
- timestamp

This is capped to 50 entries and converted into `# SESSION CONTEXT` text for prompts.

Source:

- recording and prompt context text: [orchestrator/sessionContext.py](../orchestrator/sessionContext.py)
- where records are written from tool execution: [orchestrator/agent/session.py](../orchestrator/agent/session.py)

## Skills History

STM manager maintains `active_skills` with TTL:

- schema: `{ skill_name: { content, ttl } }`
- default TTL: `2`
- decremented each iteration in stateless mode
- removed when expiring

Source:

- skill registration and TTL logic: [orchestrator/agent/stm/manager.py](../orchestrator/agent/stm/manager.py)
- per-iteration TTL tick: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py)

Note on current implementation:

- `register_skill(...)` exists in STM manager.
- there is currently no direct call site in the agent flow wiring this method.
- this means skill TTL/history support is present in STM, but population depends on future or external integration.

## Agent State

Agent state is defined by `AgentState`.

Fields:

- `task`: current objective/task text
- `completed_steps`: chronological completed/failed step summaries
- `current_objective`: immediate next objective
- `artifacts`: extracted directory paths/artifacts
- `important_facts`:
  - `task_constraints`
  - `agent_notes`
- `status`: default `in_progress`

Source:

- state model: [orchestrator/agent/stm/state.py](../orchestrator/agent/stm/state.py)

## Agent State Update Paths

## Initialization

At start of stateless execution, STM state is initialized with:

- task
- whether patient data exists (`task_constraints.patient_data_available`)
- initial artifact directories from input image paths

Source:

- init flow: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py)
- initializer: [orchestrator/agent/stm/manager.py](../orchestrator/agent/stm/manager.py)

## Automatic updates after tool calls

On each tool completion/failure (stateless mode):

- append completed/failed step to `completed_steps`
- extract artifact directories from tool result payloads
- prune notes if token budget exceeded

Source:

- update call sites: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py), [orchestrator/agent/confirmation.py](../orchestrator/agent/confirmation.py)
- update implementation: [orchestrator/agent/stm/manager.py](../orchestrator/agent/stm/manager.py)

## LLM-driven updates (STM built-in tools)

In stateless mode, the LLM can call:

- `update_agent_notes(key, value)`
- `set_next_objective(objective)`

These calls are intercepted as built-ins and update STM manager directly.
In stateful mode, these tools are rejected/unavailable.

Source:

- built-in schemas: [orchestrator/agent/stm/tools.py](../orchestrator/agent/stm/tools.py)
- execution intercepts and mode guard: [orchestrator/agent/execution.py](../orchestrator/agent/execution.py)
- confirmation drain path and mode guard: [orchestrator/agent/confirmation.py](../orchestrator/agent/confirmation.py)

## Quick End-to-End Summary

Stateless mode:

1. STM tools are exposed.
2. Agent state initializes on first iteration.
3. State text is prepended to prompt every iteration.
4. Recent tool results are included in eval context.
5. LLM updates notes/objective through STM built-ins.
6. State is updated automatically after each tool result.

Stateful mode:

1. STM tools are not exposed.
2. No STM state text is prepended.
3. Gemini chat history and function responses maintain continuity.
4. Generic eval template is used.
