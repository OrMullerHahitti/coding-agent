# Security Model

This guide explains the security infrastructure that protects against common attack vectors when the agent interacts with the file system, shell, and Python runtime.

## Overview

The Coding Agent implements defense-in-depth security:

```
┌─────────────────────────────────────────────────────┐
│                  User Confirmation                   │
│        (human approval for dangerous ops)            │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│              Auto-Approval Patterns                  │
│        (skip confirmation for safe patterns)         │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│                Input Validation                      │
│     PathValidator | CommandValidator | CodeValidator │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│                 Sandboxed Execution                  │
│       (restricted builtins, blocked imports)         │
└─────────────────────────────────────────────────────┘
```

## Path Validation

The `PathValidator` prevents directory traversal attacks.

### How It Works

```python
from coding_agent.tools.security import PathValidator, PathTraversalError

validator = PathValidator(allowed_roots=["/home/user/project"])

# safe paths - returns resolved Path
validator.validate("./src/main.py")     # OK
validator.validate("src/../src/main.py") # OK (resolves within root)

# blocked paths - raises PathTraversalError
validator.validate("../../../etc/passwd")  # BLOCKED
validator.validate("/etc/passwd")          # BLOCKED (outside roots)
```

### Configuration

```python
from coding_agent.tools.filesystem import configure_allowed_paths

# set allowed directories
configure_allowed_paths([
    "/home/user/project",
    "/tmp/workspace",
])
```

### Default Behavior

- Current working directory is always allowed
- Paths are resolved to absolute before checking
- Symlinks are resolved to detect traversal

### PathTraversalError

```python
from coding_agent.exceptions import PathTraversalError

try:
    validator.validate("../../../etc/passwd")
except PathTraversalError as e:
    print(f"Blocked: {e}")  # "Path '../../../etc/passwd' is outside allowed directories"
```

## Command Validation

The `SecureCommandRunner` prevents dangerous shell command execution.

### Blocked Commands (Default)

| Category | Commands |
|----------|----------|
| Deletion | `rm`, `rmdir`, `del`, `shred` |
| Disk ops | `mkfs`, `dd`, `fdisk`, `mount`, `umount` |
| Permissions | `chmod`, `chown`, `chgrp` |
| Privilege | `sudo`, `su`, `doas`, `pkexec` |
| System | `shutdown`, `reboot`, `init`, `systemctl` |
| Network | `curl`, `wget` (optional) |

### Blocked Patterns

These shell injection patterns are always blocked:

| Pattern | Example | Risk |
|---------|---------|------|
| `;` | `ls; rm -rf /` | command chaining |
| `&&` | `ls && rm -rf /` | conditional execution |
| `\|\|` | `false \|\| rm -rf /` | fallback execution |
| `\|` | `cat file \| mail attacker` | piping |
| `` ` `` | `` ls `rm -rf /` `` | command substitution |
| `$(...)` | `ls $(rm -rf /)` | command substitution |
| `>`, `>>` | `echo x > /etc/passwd` | output redirection |
| `<` | `mail < /etc/passwd` | input redirection |
| newlines | multiline injection | command injection |

### Configuration

```python
from coding_agent.tools.system import configure_command_runner

configure_command_runner(
    timeout=120,              # seconds (default: 60)
    allow_network=True,       # enable curl/wget
    allow_delete=False,       # keep rm blocked
    additional_blocked={"git"},  # block additional commands
    additional_allowed={"docker"},  # explicitly allow commands
)
```

### Usage

```python
from coding_agent.tools.security import get_command_runner, DisallowedCommandError

runner = get_command_runner()

# safe command
stdout, stderr, returncode = runner.execute("ls -la")

# blocked command
try:
    runner.execute("rm -rf /")
except DisallowedCommandError as e:
    print(f"Blocked: {e.reason}")  # "Command 'rm' is blocked"

# blocked pattern
try:
    runner.execute("ls; rm -rf /")
except DisallowedCommandError as e:
    print(f"Blocked: {e.reason}")  # "Command contains disallowed pattern: ';'"
```

### No Shell Mode

Commands run with `shell=False`:

```python
# internally, command is split into arguments
subprocess.run(["ls", "-la"], shell=False, ...)
```

This prevents shell interpretation of special characters.

## Python Code Validation

The `PythonCodeValidator` uses AST analysis to block dangerous code patterns.

### Blocked Imports (19 modules)

| Category | Modules |
|----------|---------|
| System | `os`, `subprocess`, `shutil`, `pathlib`, `sys`, `platform` |
| Network | `socket`, `http`, `urllib`, `requests`, `httpx`, `aiohttp` |
| Serialization | `pickle`, `marshal`, `shelve` |
| Low-level | `ctypes`, `cffi`, `mmap` |
| Dynamic | `importlib`, `imp` |
| Concurrency | `multiprocessing`, `threading`, `concurrent` |

### Blocked Builtins (11+ functions)

| Category | Functions |
|----------|-----------|
| Code execution | `exec`, `eval`, `compile` |
| File access | `open`, `file` |
| Dynamic imports | `__import__` |
| Namespace access | `globals`, `locals`, `vars` |
| Attribute manipulation | `getattr`, `setattr`, `delattr` |
| Memory | `memoryview`, `bytearray` |
| Debugging | `breakpoint` |
| User input | `input` |

### Allowed Imports (21 modules)

Safe modules that can be imported:

```
math, decimal, fractions, statistics, json, re, datetime, time,
random, collections, itertools, functools, string, textwrap,
copy, pprint, dataclasses, typing, operator, enum, uuid
```

### How It Works

```python
from coding_agent.tools.python_repl import PythonCodeValidator, CodeExecutionError

validator = PythonCodeValidator()

# safe code
validator.validate("print(math.sqrt(16))")  # OK

# blocked import
try:
    validator.validate("import os; os.system('rm -rf /')")
except CodeExecutionError as e:
    print(f"Blocked: {e.reason}")  # "Import of 'os' is blocked"

# blocked builtin
try:
    validator.validate("exec('print(1)')")
except CodeExecutionError as e:
    print(f"Blocked: {e.reason}")  # "Use of 'exec' is blocked"
```

### AST-Based Detection

The validator parses code into an Abstract Syntax Tree and checks:

1. **Import statements** - `import os`, `from os import path`
2. **Function calls** - `open(...)`, `exec(...)`
3. **Attribute access** - `__builtins__`, `__import__`

### Runtime Restrictions

Even if code passes AST validation, the REPL uses restricted builtins:

```python
restricted_builtins = {
    "print": print,
    "len": len,
    "range": range,
    "list": list,
    "dict": dict,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "tuple": tuple,
    "set": set,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "any": any,
    "all": all,
    "isinstance": isinstance,
    "type": type,
    "hasattr": hasattr,
    "round": round,
    "pow": pow,
    "divmod": divmod,
    "hex": hex,
    "oct": oct,
    "bin": bin,
    "chr": chr,
    "ord": ord,
    "repr": repr,
    "format": format,
    "slice": slice,
    "iter": iter,
    "next": next,
}
```

## Auto-Approval Patterns

Skip confirmation for trusted operations:

```python
from coding_agent import CodingAgent

agent = CodingAgent(
    client=client,
    tools=tools,
    auto_approve_patterns={
        # file write patterns
        "write": [
            "tests/*",        # any file in tests/
            "*.log",          # log files
            "tmp/*",          # temp files
            ".cache/*",       # cache files
        ],
        # command patterns
        "execute": [
            "ls",             # list files
            "pwd",            # print directory
            "git status",     # git status
            "git diff",       # git diff
            "python --version",  # version check
        ],
        # code patterns
        "run_code": [
            "print",          # print statements
            "import math",    # safe imports
        ],
    }
)
```

### Pattern Matching

- Patterns use glob syntax (`*`, `?`, `[...]`)
- For commands, pattern matches the full command
- For paths, pattern matches the file path
- For code, pattern searches within the code

## Security Best Practices

### 1. Always Enable Confirmation

Never disable confirmation for dangerous operations in production:

```python
# good: uses confirmation
class WriteFileTool(BaseTool):
    REQUIRES_CONFIRMATION = True
```

### 2. Use Specific Auto-Approval Patterns

Be specific with auto-approval:

```python
# BAD: too broad
auto_approve_patterns = {
    "write": ["*"],  # approves everything!
}

# GOOD: specific patterns
auto_approve_patterns = {
    "write": ["tests/test_*.py", "logs/*.log"],
}
```

### 3. Run in Container/VM

For production deployments, run the agent in isolation:

```bash
# docker
docker run --rm -it coding-agent

# with limited filesystem access
docker run --rm -it -v $(pwd):/workspace:rw coding-agent
```

### 4. Audit API Keys

Never log or expose API keys:

```python
# BAD
logger.info(f"Using key: {api_key}")

# GOOD
logger.info(f"Using key: {api_key[:8]}...")
```

### 5. Limit Tool Access

Only provide necessary tools:

```python
# read-only agent (no dangerous tools)
from coding_agent.tools import ReadFileTool, ListDirectoryTool, CalculatorTool

tools = [
    ReadFileTool(),
    ListDirectoryTool(),
    CalculatorTool(),
]
```

## Exception Hierarchy

Security-related exceptions:

```python
from coding_agent.exceptions import (
    PathTraversalError,      # path outside allowed directories
    DisallowedCommandError,  # blocked command or pattern
    CodeExecutionError,      # blocked import or builtin
)

# these inherit from base exception classes
# and can be caught for graceful error handling
```

## Limitations

**The security model is NOT foolproof.**

These protections are defense-in-depth but should not be considered a complete sandbox:

1. **Python REPL** - Determined attackers may find bypasses through:
   - Indirect imports via allowed modules
   - Attribute access tricks
   - Memory corruption

2. **Command execution** - Some dangerous operations may slip through:
   - Allowed commands with dangerous flags
   - New commands not in blocklist

3. **Path validation** - Edge cases:
   - Race conditions (TOCTOU)
   - Symlink manipulation after validation

**For production use, combine with:**
- Container isolation (Docker, Podman)
- Filesystem restrictions (read-only mounts)
- Network isolation
- Resource limits (CPU, memory, time)
- User namespaces

## Next Steps

- [Tools Overview](./tools-overview.md) - see how tools use security
- [Custom Tools](./custom-tools.md) - implement security in custom tools
- [Configuration](./configuration.md) - configure security settings
