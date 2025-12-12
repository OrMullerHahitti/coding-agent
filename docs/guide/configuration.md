# Configuration Guide

This guide covers all configuration options for the Coding Agent.

## Configuration Sources

Configuration is loaded from multiple sources (in priority order):

1. **CLI arguments** (highest priority)
2. **Environment variables**
3. **Config file** (`config.yaml`)
4. **Defaults** (lowest priority)

## Config File

Create a `config.yaml` in your project root:

```yaml
# config.yaml

llm:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  temperature: 0.7
  max_tokens: 4096

logging:
  level: INFO

tools:
  allowed_paths:
    - ./src
    - ./tests
  command_timeout: 120
```

### LLM Configuration

```yaml
llm:
  # provider selection
  provider: anthropic  # anthropic, openai, together, google

  # model selection (overrides provider default)
  model: claude-opus-4-5-20251101

  # generation parameters
  temperature: 0.7      # 0.0 - 2.0 (varies by provider)
  top_p: 0.9           # nucleus sampling
  top_k: 40            # top-k sampling
  max_tokens: 4096     # max response length

  # stop sequences
  stop_sequences:
    - "Human:"
    - "User:"
```

### Provider-Specific Config

#### Anthropic

```yaml
llm:
  provider: anthropic
  model: claude-opus-4-5-20251101

  # extended thinking (opus/sonnet 3.5+)
  thinking_enabled: true
  thinking_budget_tokens: 10000  # min 1024

  # tool control
  tool_choice:
    type: auto  # or {"type": "tool", "name": "specific_tool"}
```

#### OpenAI

```yaml
llm:
  provider: openai
  model: gpt-4o

  # penalties
  presence_penalty: 0.0   # -2.0 to 2.0
  frequency_penalty: 0.0  # -2.0 to 2.0

  # for o1 models
  reasoning_effort: medium  # low, medium, high
```

#### Google

```yaml
llm:
  provider: google
  model: gemini-2.5-pro-preview

  # thinking features
  thinking_budget: 10000      # flash: 0-24576, pro: 128-32768
  thinking_level: high        # low or high (gemini 3 pro)
  include_thoughts: true

  # function calling
  function_calling_mode: AUTO  # AUTO, ANY, NONE
```

#### Together

```yaml
llm:
  provider: together
  model: meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo

  # sampling
  repetition_penalty: 1.0
```

## Environment Variables

### API Keys

```bash
# LLM providers
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export TOGETHER_API_KEY="..."
export GOOGLE_API_KEY="..."
export GEMINI_API_KEY="..."  # alternative for Google

# tools
export TAVILY_API_KEY="tvly-..."
```

### Agent Configuration

```bash
# default provider (overridden by config.yaml and CLI)
export LLM_PROVIDER="anthropic"

# logging level
export CODING_AGENT_LOG_LEVEL="DEBUG"
```

## Logging Configuration

### Via CLI

```bash
uv run python -m coding_agent.main --log-level DEBUG
```

### Via Environment

```bash
export CODING_AGENT_LOG_LEVEL="DEBUG"
uv run python -m coding_agent.main
```

### Via Config File

```yaml
logging:
  level: DEBUG  # DEBUG, INFO, WARNING, ERROR
```

### Log Levels

| Level | Description |
|-------|-------------|
| `DEBUG` | Everything including API calls, tool execution |
| `INFO` | Agent activity, tool calls, confirmations |
| `WARNING` | Potential issues, deprecated usage |
| `ERROR` | Errors only |

## Tool Configuration

### Filesystem - Allowed Paths

```python
from coding_agent.tools.filesystem import configure_allowed_paths

# restrict file access to specific directories
configure_allowed_paths([
    "/home/user/project/src",
    "/home/user/project/tests",
    "/tmp/workspace",
])
```

### Command Runner

```python
from coding_agent.tools.system import configure_command_runner

configure_command_runner(
    timeout=120,              # seconds (default: 60)
    allow_network=True,       # enable curl/wget
    allow_delete=False,       # keep rm blocked
    additional_blocked={"git push"},  # block additional commands
    additional_allowed={"docker"},    # allow specific commands
)
```

### Python REPL

```python
from coding_agent.tools.python_repl import PythonREPLTool

# create REPL with custom configuration
repl = PythonREPLTool(
    allowed_imports=["numpy", "pandas"],  # additional allowed modules
    blocked_imports=["xml"],              # additional blocked modules
)
```

## Auto-Approval Patterns

Skip confirmations for trusted operations:

```python
from coding_agent import CodingAgent

agent = CodingAgent(
    client=client,
    tools=tools,
    auto_approve_patterns={
        # file write patterns (glob syntax)
        "write": [
            "tests/**/*.py",     # all test files
            "*.log",             # log files
            ".cache/**",         # cache directory
            "tmp/**",            # temp directory
        ],

        # command patterns (prefix match)
        "execute": [
            "ls",                # list
            "pwd",               # print directory
            "cat",               # view files
            "head",              # file start
            "tail",              # file end
            "git status",        # git status
            "git diff",          # git diff
            "git log",           # git log
            "python --version",  # version checks
            "pip list",          # package list
        ],

        # code patterns (substring match)
        "run_code": [
            "print(",            # print statements
            "len(",              # length
            "type(",             # type checking
            "import math",       # safe imports
            "import json",
            "import datetime",
        ],
    }
)
```

## Programmatic Configuration

### Creating Agent with Config

```python
from coding_agent import CodingAgent
from coding_agent.clients import create_client
from coding_agent.tools import get_default_tools

# create client with configuration
client = create_client(
    provider="anthropic",
    model="claude-opus-4-5-20251101",
    client_config={
        "temperature": 0.7,
        "max_tokens": 4096,
        "thinking_enabled": True,
        "thinking_budget_tokens": 5000,
    }
)

# create agent with tools and patterns
agent = CodingAgent(
    client=client,
    tools=get_default_tools(),
    system_prompt="You are a helpful coding assistant.",
    auto_approve_patterns={
        "write": ["tests/*"],
        "execute": ["ls", "git status"],
    }
)
```

### Custom System Prompt

```python
custom_prompt = """You are an expert Python developer.

Guidelines:
- Write clean, well-documented code
- Follow PEP 8 style guidelines
- Always include type hints
- Write tests for new functionality

Available tools: {tools}
"""

agent = CodingAgent(
    client=client,
    tools=tools,
    system_prompt=custom_prompt
)
```

### Custom Tool Set

```python
from coding_agent.tools import (
    CalculatorTool,
    ReadFileTool,
    ListDirectoryTool,
)
from my_tools import CustomTool

# minimal read-only agent
tools = [
    CalculatorTool(),
    ReadFileTool(),
    ListDirectoryTool(),
]

# agent with custom tools
tools = get_default_tools() + [
    CustomTool(),
]
```

## Server Configuration

### Basic Server Config

```bash
uv run python -m coding_agent.main --serve \
  --host 127.0.0.1 \
  --port 8000
```

### Production Server

```bash
# bind to all interfaces
uv run python -m coding_agent.main --serve \
  --host 0.0.0.0 \
  --port 8000 \
  --provider anthropic \
  --model claude-sonnet-4-5-20250929
```

### With Uvicorn Options

For advanced server configuration, use uvicorn directly:

```python
# server.py
from coding_agent.main import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=4,
        log_level="info",
        access_log=True,
    )
```

## Configuration Examples

### Development Setup

```yaml
# config.yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  temperature: 0.7

logging:
  level: DEBUG
```

```bash
uv run python -m coding_agent.main --stream --verbose
```

### Production Setup

```yaml
# config.yaml
llm:
  provider: anthropic
  model: claude-opus-4-5-20251101
  temperature: 0.3
  max_tokens: 8192

logging:
  level: WARNING
```

```bash
uv run python -m coding_agent.main --serve --host 0.0.0.0
```

### Read-Only Agent

```python
from coding_agent.tools import (
    CalculatorTool,
    ReadFileTool,
    ListDirectoryTool,
    TavilySearchTool,
)

# no write, command, or code execution tools
tools = [
    CalculatorTool(),
    ReadFileTool(),
    ListDirectoryTool(),
    TavilySearchTool(),
]

agent = CodingAgent(client=client, tools=tools)
```

### Maximum Security

```python
agent = CodingAgent(
    client=client,
    tools=tools,
    auto_approve_patterns={},  # no auto-approvals
)

# configure strict path validation
configure_allowed_paths(["/home/user/sandbox"])

# configure strict command runner
configure_command_runner(
    timeout=30,
    allow_network=False,
    allow_delete=False,
    additional_blocked={"ssh", "scp", "rsync"},
)
```

## Configuration Validation

The agent validates configuration on startup:

```python
# invalid temperature
client = create_client(
    "anthropic",
    client_config={"temperature": 5.0}  # invalid: max is 1.0
)
# raises: ValueError: temperature must be between 0.0 and 1.0

# invalid thinking budget
client = create_client(
    "anthropic",
    client_config={
        "thinking_enabled": True,
        "thinking_budget_tokens": 100  # invalid: min is 1024
    }
)
# raises: ValueError: thinking_budget_tokens must be >= 1024
```

## Next Steps

- [CLI Reference](./cli-reference.md) - command-line options
- [LLM Providers](./llm-providers.md) - provider-specific configuration
- [Security](./security.md) - security configuration
