# Human-in-the-Loop

This guide explains the interrupt and confirmation patterns that allow human oversight of agent actions.

## Overview

The Coding Agent supports two human-in-the-loop patterns:

1. **Interrupts** - Agent asks user a question and waits for response
2. **Confirmations** - Agent requests approval before dangerous operations

```
┌─────────────────────────────────────────────────┐
│              Agent Execution                     │
└─────────────────────────────────────────────────┘
           ↓                    ↓
┌──────────────────┐  ┌──────────────────────────┐
│   INTERRUPTED    │  │  AWAITING_CONFIRMATION   │
│                  │  │                          │
│ AskUserTool      │  │ WriteFileTool            │
│ needs input      │  │ RunCommandTool           │
│                  │  │ PythonREPLTool           │
└──────────────────┘  └──────────────────────────┘
           ↓                    ↓
┌──────────────────┐  ┌──────────────────────────┐
│  User provides   │  │  User confirms yes/no    │
│  response        │  │                          │
└──────────────────┘  └──────────────────────────┘
           ↓                    ↓
┌─────────────────────────────────────────────────┐
│           Agent Resumes                          │
└─────────────────────────────────────────────────┘
```

## Interrupts

### When Interrupts Happen

The `AskUserTool` raises an interrupt when the agent needs user input:

```python
# agent calls ask_user tool
agent.run("Help me with my project")

# internally, AskUserTool.execute() raises:
raise InterruptRequested(
    tool_name="ask_user",
    tool_call_id="call_123",
    question="What programming language is your project in?",
    context={}
)
```

### Handling Interrupts

```python
from coding_agent import CodingAgent

agent = CodingAgent(client, tools)

# initial request
result = agent.run("Help me optimize my code")

# check for interrupt
while result.is_interrupted:
    # display question to user
    print(f"Agent asks: {result.interrupt.question}")

    # get user response
    user_response = input("Your response: ")

    # resume with response
    result = agent.resume(
        result.interrupt.tool_call_id,
        user_response
    )

# now result is complete
print(f"Agent: {result.content}")
```

### InterruptInfo Structure

```python
@dataclass
class InterruptInfo:
    tool_name: str       # "ask_user"
    tool_call_id: str    # unique ID for resumption
    question: str        # what to ask the user
    context: dict | None # optional additional context
```

### Resume Method

```python
def resume(
    self,
    tool_call_id: str,
    user_response: str,
    stream: bool = False,
    verbose: bool = False
) -> AgentRunResult:
    """Resume after an interrupt with user's response."""
```

- `tool_call_id` must match the pending interrupt
- `user_response` becomes the tool result
- Agent continues processing from where it paused

## Confirmations

### When Confirmations Happen

Tools with `REQUIRES_CONFIRMATION = True` trigger confirmations:

```python
# agent wants to write a file
# WriteFileTool.execute() triggers confirmation check

# agent catches ConfirmationRequested:
raise ConfirmationRequested(
    tool_name="write_file",
    tool_call_id="call_456",
    message="Write 150 characters to './config.json'",
    operation="write",
    arguments={"path": "./config.json", "content": "..."}
)
```

### Tools Requiring Confirmation

| Tool | Operation Type | Confirmation Message |
|------|---------------|---------------------|
| `WriteFileTool` | `write` | "Write {len_content} characters to '{path}'" |
| `RunCommandTool` | `execute` | "Execute command: '{command}'" |
| `PythonREPLTool` | `run_code` | "Execute Python code ({len_code} characters)" |

### Handling Confirmations

```python
result = agent.run("Create a backup file")

while result.is_awaiting_confirmation:
    # display confirmation request
    print(f"Confirm: {result.confirmation.message}")

    # get user decision
    confirm = input("Approve? (y/n): ").lower() == "y"

    # resume with decision
    result = agent.resume_confirmation(
        result.confirmation.tool_call_id,
        confirmed=confirm
    )

print(f"Agent: {result.content}")
```

### ConfirmationInfo Structure

```python
@dataclass
class ConfirmationInfo:
    tool_name: str       # "write_file", "run_command", etc.
    tool_call_id: str    # unique ID for resumption
    message: str         # human-readable description
    operation: str       # "write", "execute", "run_code"
    arguments: dict      # original tool arguments
```

### Resume Confirmation Method

```python
def resume_confirmation(
    self,
    tool_call_id: str,
    confirmed: bool,
    stream: bool = False,
    verbose: bool = False
) -> AgentRunResult:
    """Resume after confirmation request."""
```

- If `confirmed=True`: tool executes with original arguments
- If `confirmed=False`: cancellation message added to history

## Auto-Approval Patterns

Skip confirmations for trusted operations:

```python
agent = CodingAgent(
    client=client,
    tools=tools,
    auto_approve_patterns={
        # file write patterns (glob syntax)
        "write": [
            "tests/*",           # test files
            "*.log",             # log files
            ".cache/*",          # cache files
            "tmp/*",             # temp files
        ],

        # command patterns (exact or prefix match)
        "execute": [
            "ls",                # list files
            "pwd",               # current directory
            "git status",        # git status
            "git diff",          # git diff
            "cat",               # view files
            "head",              # view file start
            "tail",              # view file end
        ],

        # code patterns (substring match)
        "run_code": [
            "print(",            # print statements
            "import math",       # safe imports
            "len(",              # length checks
        ],
    }
)
```

### Pattern Matching Rules

| Operation | Pattern Type | Example |
|-----------|--------------|---------|
| `write` | Glob | `tests/*.py` matches `tests/test_foo.py` |
| `execute` | Prefix | `git` matches `git status`, `git diff` |
| `run_code` | Substring | `print(` matches code containing `print(` |

## Combined Example

Complete handling of both patterns:

```python
from coding_agent import CodingAgent
from coding_agent.clients import create_client
from coding_agent.tools import get_default_tools

def run_agent_with_human_loop():
    client = create_client("anthropic")
    tools = get_default_tools()

    agent = CodingAgent(
        client=client,
        tools=tools,
        auto_approve_patterns={
            "execute": ["ls", "pwd", "cat"],
        }
    )

    # initial request
    result = agent.run("Analyze my project structure", stream=True)

    # handle all human-in-the-loop situations
    while True:
        if result.is_completed:
            print(f"\nAgent: {result.content}")
            break

        elif result.is_interrupted:
            print(f"\n[Agent asks]: {result.interrupt.question}")
            response = input("Your response: ")
            result = agent.resume(
                result.interrupt.tool_call_id,
                response,
                stream=True
            )

        elif result.is_awaiting_confirmation:
            print(f"\n[Confirm]: {result.confirmation.message}")
            confirm = input("Approve? (y/n): ").strip().lower() == "y"
            result = agent.resume_confirmation(
                result.confirmation.tool_call_id,
                confirm,
                stream=True
            )

        elif result.is_error:
            print(f"\nError: {result.error}")
            break

if __name__ == "__main__":
    run_agent_with_human_loop()
```

## Web/API Integration

### REST API Approach

For web applications, handle interrupts/confirmations via REST:

```python
# backend
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
sessions = {}  # store agent sessions

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ResumeRequest(BaseModel):
    session_id: str
    tool_call_id: str
    response: str  # or confirmed: bool for confirmations

@app.post("/chat")
def chat(req: ChatRequest):
    agent = get_or_create_agent(req.session_id)
    result = agent.run(req.message)

    if result.is_interrupted:
        return {
            "status": "interrupted",
            "question": result.interrupt.question,
            "tool_call_id": result.interrupt.tool_call_id
        }
    elif result.is_awaiting_confirmation:
        return {
            "status": "awaiting_confirmation",
            "message": result.confirmation.message,
            "tool_call_id": result.confirmation.tool_call_id
        }
    else:
        return {
            "status": "completed",
            "content": result.content
        }

@app.post("/resume")
def resume(req: ResumeRequest):
    agent = sessions[req.session_id]
    result = agent.resume(req.tool_call_id, req.response)
    # ... handle result similarly
```

### WebSocket Approach

For real-time applications:

```python
@app.websocket("/ws/{session_id}")
async def websocket_chat(websocket, session_id: str):
    agent = get_or_create_agent(session_id)

    while True:
        data = await websocket.receive_json()

        if data["type"] == "message":
            result = agent.run(data["content"], stream=True)
        elif data["type"] == "resume":
            result = agent.resume(data["tool_call_id"], data["response"])
        elif data["type"] == "confirm":
            result = agent.resume_confirmation(
                data["tool_call_id"],
                data["confirmed"]
            )

        # send result status
        await websocket.send_json({
            "type": result.state.value,
            "content": result.content,
            "interrupt": result.interrupt.__dict__ if result.interrupt else None,
            "confirmation": result.confirmation.__dict__ if result.confirmation else None,
        })
```

## Creating Custom Interrupt Tools

```python
from coding_agent.tools.base import BaseTool
from coding_agent.exceptions import InterruptRequested

class ChoiceTool(BaseTool):
    """let user choose from options"""

    INTERRUPT_TOOL = True  # mark as interrupt tool

    @property
    def name(self) -> str:
        return "choose_option"

    @property
    def description(self) -> str:
        return "Present options to user and get their choice"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["question", "options"]
        }

    def execute(self, question: str, options: list[str], **kwargs) -> str:
        tool_call_id = kwargs.get("_tool_call_id", "unknown")

        # format question with options
        formatted = f"{question}\n"
        for i, opt in enumerate(options, 1):
            formatted += f"  {i}. {opt}\n"

        raise InterruptRequested(
            tool_name=self.name,
            tool_call_id=tool_call_id,
            question=formatted,
            context={"options": options}
        )
```

## Best Practices

### 1. Always Handle Both Patterns

```python
# handle all possible states
while not result.is_completed and not result.is_error:
    if result.is_interrupted:
        # handle interrupt
    elif result.is_awaiting_confirmation:
        # handle confirmation
```

### 2. Preserve Context

```python
# store state for multi-turn interactions
session_state = {
    "agent": agent,
    "last_result": result,
    "conversation_id": "...",
}
```

### 3. Timeout Handling

```python
import asyncio

async def get_user_response_with_timeout(question, timeout=300):
    try:
        return await asyncio.wait_for(
            get_user_input(question),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        return None  # or default response
```

### 4. Graceful Cancellation

```python
# user can cancel pending operations
if user_wants_to_cancel:
    agent.clear_history()  # clears pending state
    # or start fresh conversation
```

## Next Steps

- [Tools Overview](./tools-overview.md) - see which tools use these patterns
- [Custom Tools](./custom-tools.md) - create tools with confirmation
- [Security](./security.md) - understand why confirmations matter
