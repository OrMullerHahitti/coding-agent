# Tools Overview

This guide documents all built-in tools available in the Coding Agent.

## Default Tools

The agent comes with 8 built-in tools:

| Tool | Purpose | Requires Confirmation |
|------|---------|----------------------|
| `calculator` | Basic arithmetic | No |
| `list_directory` | List directory contents | No |
| `read_file` | Read file contents | No |
| `write_file` | Write to files | **Yes** |
| `run_command` | Execute shell commands | **Yes** |
| `python_repl` | Execute Python code | **Yes** |
| `web_search` | Search the web | No |
| `ask_user` | Ask user questions | No (interrupts) |

## Tool Reference

### CalculatorTool

Performs basic arithmetic operations.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `operation` | string | Yes | One of: "add", "subtract", "multiply", "divide" |
| `a` | number | Yes | First operand |
| `b` | number | Yes | Second operand |

**Returns:** Result as a number, or error message for division by zero.

**Example:**
```
User: What is 15 multiplied by 7?
Agent: [calls calculator(operation="multiply", a=15, b=7)]
       The result is 105.
```

---

### ListDirectoryTool

Lists contents of a directory.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `path` | string | No | "." | Directory path to list |

**Returns:** List of filenames, one per line.

**Security:** Path is validated to prevent directory traversal attacks.

**Example:**
```
User: What's in the src folder?
Agent: [calls list_directory(path="./src")]
       The src folder contains:
       - agent.py
       - main.py
       - tools/
       - clients/
```

---

### ReadFileTool

Reads the contents of a file.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | Yes | File path to read |

**Returns:** File contents as string, or error message.

**Security:**
- Path validated against traversal attacks
- UTF-8 decoding with error handling
- Returns error for binary files

**Example:**
```
User: Show me the contents of README.md
Agent: [calls read_file(path="./README.md")]
       Here's the README content:
       # Project Title
       ...
```

---

### WriteFileTool

Writes content to a file.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | Yes | File path to write |
| `content` | string | Yes | Content to write |

**Returns:** Success message with character count, or error.

**Security:**
- **Requires confirmation** before execution
- Path validated against traversal attacks
- Creates parent directories if needed

**Confirmation prompt:**
```
[Confirm]: Write 156 characters to './output.txt' (y/n):
```

**Example:**
```
User: Create a hello.py file with a hello world function
Agent: [calls write_file(path="./hello.py", content="def hello():\n    print('Hello, World!')\n")]
       [Confirm]: Write 42 characters to './hello.py' (y/n): y
       Created hello.py with a hello world function.
```

---

### RunCommandTool

Executes shell commands.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `command` | string | Yes | Command to execute (no shell operators) |

**Returns:** Combined stdout and stderr output.

**Security:**
- **Requires confirmation** before execution
- Blocked commands: `rm`, `rmdir`, `sudo`, `chmod`, `chown`, `shutdown`, etc.
- Blocked patterns: `;`, `&&`, `|`, `` ` ``, `$(...)`, `>`, `<`
- 60-second timeout
- No shell interpretation (`shell=False`)

**Confirmation prompt:**
```
[Confirm]: Execute command: 'git status' (y/n):
```

**Blocked Commands (default):**
- Deletion: `rm`, `rmdir`, `del`, `shred`
- Disk operations: `mkfs`, `dd`, `fdisk`, `mount`, `umount`
- Permissions: `chmod`, `chown`, `chgrp`
- Privilege escalation: `sudo`, `su`, `doas`, `pkexec`
- System control: `shutdown`, `reboot`, `init`, `systemctl`
- Network (optional): `curl`, `wget`

**Example:**
```
User: Run git status
Agent: [calls run_command(command="git status")]
       [Confirm]: Execute command: 'git status' (y/n): y
       On branch main
       nothing to commit, working tree clean
```

---

### PythonREPLTool

Executes Python code in a sandboxed environment.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `code` | string | Yes | Python code to execute |

**Returns:** Captured stdout output, or error message.

**Security:**
- **Requires confirmation** before execution
- AST-based validation before execution
- Blocked imports (19 modules): `os`, `subprocess`, `socket`, `requests`, etc.
- Blocked builtins (11 functions): `exec`, `eval`, `open`, `__import__`, etc.
- Allowed imports (21 modules): `math`, `json`, `datetime`, `collections`, etc.
- Persistent namespace (state preserved across calls)

**Confirmation prompt:**
```
[Confirm]: Execute Python code (87 characters) (y/n):
```

**Allowed Imports:**
`math`, `decimal`, `fractions`, `statistics`, `json`, `re`, `datetime`, `time`, `random`, `collections`, `itertools`, `functools`, `string`, `textwrap`, `copy`, `pprint`, `dataclasses`, `typing`, `operator`, `enum`, `uuid`

**Blocked Imports:**
`os`, `subprocess`, `shutil`, `pathlib`, `socket`, `http`, `urllib`, `requests`, `httpx`, `aiohttp`, `pickle`, `marshal`, `shelve`, `ctypes`, `cffi`, `mmap`, `importlib`, `imp`, `sys`, `platform`, `multiprocessing`, `threading`, `concurrent`

**Example:**
```
User: Calculate the first 10 Fibonacci numbers
Agent: [calls python_repl(code="...")]
       [Confirm]: Execute Python code (156 characters) (y/n): y
       [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
```

---

### TavilySearchTool

Searches the web for information.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | Search query |

**Returns:** Formatted search results with title, URL, and content snippet.

**Requirements:** Requires `TAVILY_API_KEY` environment variable.

**Example:**
```
User: Search for Python async best practices
Agent: [calls web_search(query="Python async best practices 2024")]
       Here are the top results:

       **Async Python Best Practices**
       https://example.com/...
       Content: When using async/await in Python...
```

---

### AskUserTool

Asks the user a question and waits for a response.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `question` | string | Yes | Question to ask the user |

**Returns:** User's response.

**Behavior:**
- Raises `InterruptRequested` exception
- Agent returns with `INTERRUPTED` state
- Caller provides response via `agent.resume()`

**Example:**
```
User: Help me refactor this code
Agent: [calls ask_user(question="Should I prioritize readability or performance?")]
       [Agent asks]: Should I prioritize readability or performance?
       Your response: Readability
Agent: I'll focus on making the code more readable...
```

## Getting Default Tools

```python
from coding_agent.tools import get_default_tools

tools = get_default_tools()
# Returns: [CalculatorTool, ListDirectoryTool, ReadFileTool,
#           WriteFileTool, RunCommandTool, PythonREPLTool,
#           TavilySearchTool, AskUserTool]
```

## Using Specific Tools

```python
from coding_agent.tools import (
    CalculatorTool,
    ReadFileTool,
    WriteFileTool,
    RunCommandTool,
    PythonREPLTool,
)

# create custom tool set
tools = [
    CalculatorTool(),
    ReadFileTool(),
    # omit write/command tools for read-only agent
]
```

## Tool Schema Format

Each tool provides a JSON schema for the LLM:

```python
tool = CalculatorTool()
schema = tool.to_schema()
# {
#     "type": "function",
#     "function": {
#         "name": "calculator",
#         "description": "Perform basic arithmetic operations",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "operation": {"type": "string", "enum": ["add", "subtract", ...]},
#                 "a": {"type": "number", "description": "First operand"},
#                 "b": {"type": "number", "description": "Second operand"}
#             },
#             "required": ["operation", "a", "b"]
#         }
#     }
# }
```

## Next Steps

- [Custom Tools](./custom-tools.md) - create your own tools
- [Security](./security.md) - understand the security model
- [Human-in-the-Loop](./human-in-the-loop.md) - learn about interrupts and confirmations
