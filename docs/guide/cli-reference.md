# CLI Reference

Complete reference for the Coding Agent command-line interface.

## Basic Usage

```bash
# start interactive REPL
uv run python -m coding_agent.main

# start API server
uv run python -m coding_agent.main --serve
```

## Command-Line Arguments

### Provider Options

| Argument | Description | Default |
|----------|-------------|---------|
| `--provider` | LLM provider to use | auto-detect |
| `--model` | Model name | provider default |

**Provider choices:** `anthropic`, `openai`, `together`, `google`

```bash
# use specific provider
uv run python -m coding_agent.main --provider anthropic

# use specific model
uv run python -m coding_agent.main --provider openai --model gpt-4-turbo

# use together with Llama
uv run python -m coding_agent.main --provider together --model meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo
```

### Output Options

| Argument | Description | Default |
|----------|-------------|---------|
| `--stream` | Enable streaming responses | disabled |
| `--verbose` | Show reasoning and tool calls | disabled |

```bash
# enable streaming
uv run python -m coding_agent.main --stream

# enable verbose output
uv run python -m coding_agent.main --verbose

# both together
uv run python -m coding_agent.main --stream --verbose
```

### Logging Options

| Argument | Description | Default |
|----------|-------------|---------|
| `--log-level` | Logging verbosity | `WARNING` |

**Log level choices:** `DEBUG`, `INFO`, `WARNING`, `ERROR`

```bash
# debug logging (most verbose)
uv run python -m coding_agent.main --log-level DEBUG

# info logging
uv run python -m coding_agent.main --log-level INFO
```

### Server Options

| Argument | Description | Default |
|----------|-------------|---------|
| `--serve` | Start API server instead of REPL | disabled |
| `--host` | Server host address | `127.0.0.1` |
| `--port` | Server port | `8000` |

```bash
# start server on default port
uv run python -m coding_agent.main --serve

# custom host and port
uv run python -m coding_agent.main --serve --host 0.0.0.0 --port 3000
```

### Utility Options

| Argument | Description |
|----------|-------------|
| `--visualize` | Print agent structure as Mermaid diagram and exit |

```bash
# visualize agent structure
uv run python -m coding_agent.main --visualize
```

## Provider Auto-Detection

When `--provider` is not specified, the CLI detects providers in this order:

1. **Config file**: `llm.provider` in `config.yaml`
2. **Environment variable**: `LLM_PROVIDER`
3. **Available API key** (first found):
   - `ANTHROPIC_API_KEY` → anthropic
   - `OPENAI_API_KEY` → openai
   - `TOGETHER_API_KEY` → together
   - `GOOGLE_API_KEY` → google

## Interactive REPL

### Starting the REPL

```bash
uv run python -m coding_agent.main
```

Output:
```
Coding Agent v1.0.0
Provider: anthropic (claude-sonnet-4-5-20250929)
Type 'exit' or 'quit' to quit.

You:
```

### REPL Commands

| Input | Action |
|-------|--------|
| `exit` | Exit the REPL |
| `quit` | Exit the REPL |
| `Ctrl+C` | Cancel current operation or exit |
| Any text | Send message to agent |

### REPL Interaction Example

```
You: What files are in the current directory?

Agent: I'll list the directory contents for you.

[Tool Call]: list_directory(path=".")

The current directory contains:
- src/
- tests/
- README.md
- pyproject.toml
- config.yaml

You: Read the README

[Tool Call]: read_file(path="./README.md")

Here's the README content:
# Coding Agent
...

You: Create a file called hello.py

[Confirm]: Write 42 characters to './hello.py' (y/n): y

Agent: Created hello.py with a simple hello world function.

You: exit
Goodbye!
```

### Handling Interrupts

When the agent asks a question:

```
You: Help me fix this code

[Agent asks]: What programming language is the code in?
Your response: Python

Agent: I'll analyze the Python code...
```

### Handling Confirmations

When the agent needs approval:

```
You: Delete all .log files

[Confirm]: Execute command: 'find . -name "*.log" -delete' (y/n): n

Agent: Understood, I won't delete the log files.
```

## API Server Mode

### Starting the Server

```bash
uv run python -m coding_agent.main --serve
```

Output:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### API Endpoints

#### Health Check

```bash
curl http://localhost:8000/health
```

#### Chat (POST)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "stream": false}'
```

#### WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.send(JSON.stringify({ message: "Hello!", stream: true }));
```

### Server with Custom Config

```bash
# production-like setup
uv run python -m coding_agent.main --serve \
  --host 0.0.0.0 \
  --port 3000 \
  --provider anthropic \
  --model claude-opus-4-5-20251101
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic (Claude) API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `TOGETHER_API_KEY` | Together AI API key |
| `GOOGLE_API_KEY` | Google (Gemini) API key |
| `GEMINI_API_KEY` | Alternative for Google API key |
| `TAVILY_API_KEY` | Tavily search API key |
| `LLM_PROVIDER` | Default provider selection |
| `CODING_AGENT_LOG_LEVEL` | Default log level |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Authentication error |

## Examples

### Basic Chat

```bash
uv run python -m coding_agent.main
```

### Development Mode

```bash
uv run python -m coding_agent.main --stream --verbose --log-level DEBUG
```

### Production Server

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
uv run python -m coding_agent.main --serve --host 0.0.0.0 --port 8000
```

### Using Different Providers

```bash
# Claude
uv run python -m coding_agent.main --provider anthropic --model claude-opus-4-5-20251101

# GPT-4
uv run python -m coding_agent.main --provider openai --model gpt-4o

# Gemini
uv run python -m coding_agent.main --provider google --model gemini-2.5-pro-preview

# Llama via Together
uv run python -m coding_agent.main --provider together --model meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
```

### Combining Options

```bash
# streaming with verbose logging
uv run python -m coding_agent.main \
  --provider anthropic \
  --model claude-sonnet-4-5-20250929 \
  --stream \
  --verbose \
  --log-level INFO
```

## Troubleshooting

### "No provider available"

```bash
# check if API keys are set
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY

# explicitly specify provider
uv run python -m coding_agent.main --provider anthropic
```

### "Authentication failed"

```bash
# verify API key is correct
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
uv run python -m coding_agent.main --provider anthropic
```

### "Connection refused" (server mode)

```bash
# check if port is in use
lsof -i :8000

# use different port
uv run python -m coding_agent.main --serve --port 8001
```

### Debug Logging

```bash
# enable debug output to see what's happening
uv run python -m coding_agent.main --log-level DEBUG
```

## Next Steps

- [Configuration](./configuration.md) - detailed configuration options
- [Getting Started](./getting-started.md) - quick start guide
- [LLM Providers](./llm-providers.md) - provider-specific options
