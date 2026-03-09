[Agent Documentation]

## Purpose & Role

The agent is an orchestrator agent, with the LLM (more precisely gemini), acting as the core orchestrator responsible for executing tasks, making decisions, and using tools. It acts autonomously or collaboratively, depending on the selected mode.

## Agent Architecture

![Agent Architecture](assets/agent-architecture.png)

### Overview

The agent architecture is designed for modularity, extensibility, and robust orchestration of tasks using an LLM at its core. The main components and their interactions are as follows:

#### 1. AgenticAgent

The [AgenticAgent](../orchestrator/agentic_agent.py) is the central controller. It is responsible for:

- Managing the agent workflow and iterative decision-making loop.
- Registering and selecting tools dynamically.
- Maintaining session context and history for continuity.
- Interfacing with the LLM (Large Language Model) for reasoning and orchestration.
- Communicating with MCPs (Model Context Protocol servers) and the Skills MCP for external capabilities.

#### 2. LLM (Large Language Model)

The current implementation uses the Gemini LLM as the reasoning engine of the agent. It processes the goal and make informed decisions about which tools to use and what actions to take next. The LLM operates in a session mode, retaining access to the full session context across all steps.

#### 3. Tool Registry

Tools are registered and discovered dynamically via the [tool_registry.py](../orchestrator/tool_registry.py) module. This allows the agent to flexibly add or remove capabilities without changing core logic. The registry is also responsible for executing tools and maintaining their connections.

#### 4. MCPs

The available MCPs are the following:
- MCP Skills: Provides access to agent skills that the agent can invoke as needed (e.g., text processing, workflow automation).
- MCP Monai: Handles medical image analysis tasks, such as segmentation and detection, using MONAI models.
- MCP Utils: Offers utility functions and services, such as DICOM parsing and data preprocessing, to support other MCPs and agent workflows.
- MCP Radlex: Provides medical terminology and ontology services, such as filling structured report templates using RadLex terms.

All tools available are detailed in [Tools](tools.md).

#### 5. Database

The agent uses a SQLite database to store session context, tool call history and files. [TODO]

#### 6. Task Runner

The Task Runner is responsible for managing long-running or background operations, such as MONAI inference or report generation. It ensures that these tasks are executed efficiently and that their results are properly integrated back into the agent's workflow.

There are some hardcoded tasks that go into the task runner, such as MONAI inference and report generation, but the task runner is designed to be extensible to support additional long-running tasks as needed. The agent can also decide to use the task runner for any task that it deems necessary, even if it's not hardcoded, by simply calling the task runner tool and providing the necessary parameters.

## Agent Modes

- Analysis Agent: Acts as a chatbot assistant where the user can ask questions and the agent will use tools to answer them.
- Autonomous Agent: Receives files/folders as input and performs a series of tasks, the agent will decide which tools to use and in which order, and will perform the tasks without user intervention The goal is predefined and the agent will decide how to achieve it.

## Agent Capabilities

- Tool Usage: Can use registered tools for tasks like image analysis, report generation, data parsing
- Skill Invocation: Can invoke skills

## Interaction Scenarios

The orchestrator supports three interaction scenarios:

### Scenario 1 — Assisted Analysis

User query + uploaded files → Agent

Input:

- User text
- Uploaded files
- System prompt

Output:

- Analysis referencing uploaded data

### Scenario 2 — Autonomous Processing

File/folder submission → Agent

Input:

- File paths
- Predefined goal
- System prompt

Output (what should do, now is not functioning correctly, just started working on):

- Analysis results
- Generated reports

### Scenario 3 — Interactive Analysis

User → Agent query

Input:

- User text
- Session context
- System prompt

Output:

- Agent response

## Agent Triggers

The orchestrator activates the agent when one of the following events occurs:

- user query submitted via the interface
- file or folder upload also via the interface

Currently, external applications cannot trigger the agent through structured events (e.g., notifications from health systems). This may be added in future versions.

## Agent Workflow

The agent workflow is an iterative loop orchestrated by the LLM:

1. A goal is set—either predefined (autonomous mode) or provided by the user (chatbot mode).
2. The agent sends the goal and the current session context (if in database, see [Session](#session) section) to the LLM, which determines the next action and selects the appropriate tool to use.
3. The agent executes the tool as instructed by the LLM and collects the result.
4. The result is returned to the LLM, which evaluates progress toward the goal and decides the next step.
5. This loop continues until the LLM determines the goal is achieved, at which point the workflow ends.

![Agent Workflow](assets/agent-workflow.png)
## Session

The LLM operates in session mode (statefull mode), maintaining access to the session context across all steps. This means context is preserved between actions—no information is lost, and only the tool result needs to be sent after each step.

**Advantages:**

- The LLM can make more informed decisions by leveraging the full session history.
- Conversation flow and context are maintained, improving continuity and accuracy.

**Trade-offs:**

- Retaining all previous interactions can increase token usage and operational costs.
- Very long sessions may introduce confusion or hallucinations if irrelevant context accumulates.


## Agent Context

The agent does not maintain persistent memory across sessions, but it does retain session context during an active session. When returning to a previous conversation, only the history of tool calls and their summarized results are restored. This session context is stored in a SQLite database.

The session context, like explained before, is all in gemini once the session starts, each message sent to gemini will have access to the full session context, which includes all previous information during the session.

## System prompt

The agent uses a system prompt that is defined in [gemini_client.py](../orchestrator/gemini_client.py) to guide the LLM's behavior and decision-making process. The system prompt provides instructions, guidelines, and constraints for how the LLM should operate within the agent's workflow. The system prompt explains the agent's capabilities, the tools available, and how to use them effectively to achieve the goals set by the user or predefined for autonomous operation. Also explains the skill progressive disclosure, so agent knows how to interact with the skills MCP to access the skills when needed.

For autonomous agent, the system prompt maybe needs changes due to different focus, does not have human in the loop, so it needs to be more focused on how to achieve the goal using the tools and skills available, and less focused on how to interact with the user.

## Tool Registry & Skill Management

Tools are dynamically registered and discovered via the [tool_registry.py](../orchestrator/tool_registry.py) module.

Skills are access by the skills MCP server.

For details of each MCP, see each MCP README.

## Extensibility (adding MCPS)

The agent is designed to be extensible, allowing new tools and skills to be added with minimal changes to the core logic.

### Adding MCPS

To add a new MCP, the mcp configuration needs to be in the [mcp-config.json](../orchestrator/mcp-config.json) file. After having it configured in the json file. Can be reloaded via interface or by restarting the application the mcp should be available to the agent. The configuration of the mcp should follow this structure:

If the mcp is of type http, it should follow this structure:

```json

{
  "mcp-name": {
    "url": "http://mcp-url",
    "type": "http",
  }
}
```

if the mcp is of type stdio, it should follow this structure:

```json
{
  "mcp-name": {
    "command": "command to start the mcp",
    "args": ["arg1", "arg2"],
    "type": "stdio"
  }
}
```

if the mcp has any env variables, it should follow this structure:

```json
{
  "mcp-name": {
    "url": "http://mcp-url",
    "type": "http",
    "env": {
        "ENV_VAR_NAME": "value"
    }
  }
}
```


## Logging

For debugging purposes, the agent maintains detailed logs of its interactions, including:

- whats being sent to the LLM
- whats being received from the LLM
- what tools are being used
- the results of the tools

They are per session, and are stored in [logs](../orchestrator/logs) folder.

