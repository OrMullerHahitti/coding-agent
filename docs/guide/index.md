# Coding Agent Documentation

Welcome to the Coding Agent documentation. This guide covers everything you need to use, configure, and extend the agent.

## Quick Links

| Guide | Description |
|-------|-------------|
| [Getting Started](./getting-started.md) | Installation, setup, and first steps |
| [CLI Reference](./cli-reference.md) | Command-line options and usage |

## Core Concepts

| Guide | Description |
|-------|-------------|
| [Agent Architecture](./agent-architecture.md) | ReAct loop, states, and message flow |
| [Streaming](./streaming.md) | Real-time response streaming |
| [Human-in-the-Loop](./human-in-the-loop.md) | Interrupts and confirmations |

## Tools

| Guide | Description |
|-------|-------------|
| [Tools Overview](./tools-overview.md) | Built-in tools reference |
| [Custom Tools](./custom-tools.md) | Creating your own tools |
| [Security](./security.md) | Path, command, and code validation |

## LLM Providers

| Guide | Description |
|-------|-------------|
| [LLM Providers](./llm-providers.md) | Supported providers and configuration |
| [Adding Providers](./adding-providers.md) | How to add new LLM providers |

## Configuration

| Guide | Description |
|-------|-------------|
| [Configuration](./configuration.md) | Config file, environment, and options |

## Learning Path

### For New Users

1. Start with [Getting Started](./getting-started.md)
2. Learn about [Tools Overview](./tools-overview.md)
3. Understand [Human-in-the-Loop](./human-in-the-loop.md)
4. Reference the [CLI Reference](./cli-reference.md)

### For Developers

1. Understand [Agent Architecture](./agent-architecture.md)
2. Learn [Custom Tools](./custom-tools.md)
3. Study [Security](./security.md)
4. Explore [Adding Providers](./adding-providers.md)

### For DevOps

1. Review [Configuration](./configuration.md)
2. Check [CLI Reference](./cli-reference.md) for server mode
3. Understand [Security](./security.md) for production

## Quick Examples

### Start Interactive Chat

```bash
uv run python -m coding_agent.main --stream
```

### Start API Server

```bash
uv run python -m coding_agent.main --serve --port 8000
```

### Use Specific Provider

```bash
uv run python -m coding_agent.main --provider anthropic --model claude-opus-4-5-20251101
```

### Programmatic Usage

```python
from coding_agent import CodingAgent
from coding_agent.clients import create_client
from coding_agent.tools import get_default_tools

client = create_client("anthropic")
agent = CodingAgent(client=client, tools=get_default_tools())

result = agent.run("List files in current directory")
print(result.content)
```

## Project Structure

```
src/coding_agent/
├── agent.py           # main CodingAgent class
├── main.py            # CLI entry point
├── stream_handler.py  # streaming response handling
├── types.py           # unified types
├── exceptions.py      # exception hierarchy
├── prompts.py         # system prompts
├── clients/           # LLM provider implementations
│   ├── base.py        # BaseLLMClient
│   ├── factory.py     # client factory
│   ├── anthropic.py   # Claude
│   ├── openai.py      # GPT
│   ├── google.py      # Gemini
│   └── together.py    # Together AI
└── tools/             # tool implementations
    ├── base.py        # BaseTool
    ├── security.py    # validators
    ├── filesystem.py  # file operations
    ├── system.py      # shell commands
    ├── python_repl.py # Python execution
    ├── search.py      # web search
    ├── calculator.py  # math operations
    └── ask_user.py    # human-in-the-loop
```

## Getting Help

- Check the specific guide for your topic
- Review the [CLI Reference](./cli-reference.md) troubleshooting section
- Look at the source code in `src/coding_agent/`
