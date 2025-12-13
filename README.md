# Coding Agent

A powerful, provider-agnostic autonomous coding agent using a ReAct (Reasoning, Acting, Observing) loop. Supports multiple LLM providers through a unified interface.

## Features

- **Multi-Provider Support**: Seamlessly switch between Anthropic (Claude), OpenAI, Google Gemini, and Together AI
- **Tool Use**: Equipped with tools for file manipulation, system commands, Python REPL, and web search
- **Streaming**: Real-time streaming responses with reasoning display
- **Multi-Agent Mode**: Optional supervisor + specialist workers (configured in `config.yaml`)
- **Human-in-the-Loop**: Interrupt pattern for agent-user clarification via `ask_user` tool
- **Security**: Path validation, command sanitization, and Python code inspection
- **API Server**: Optional FastAPI server (`--serve`)
- **Data Analysis Tools**: Dedicated dataset tools (CSV/JSON/JSONL/XLSX, export, plot saving)
- **Configuration**: Easy configuration via `config.yaml`, environment variables, or CLI flags

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       CodingAgent                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │   History   │  │ StreamHandler│  │   Tool Registry │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Client Factory                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Anthropic│ │  OpenAI  │ │  Google  │ │   Together   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Language**: Python 3.12+
- **Dependency Management**: `uv`
- **LLM Clients**: `anthropic`, `openai`, `google-genai`, `together`
- **Search**: `tavily-python`

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/OrMullerHahitti/coding-agent/
   cd coding-agent
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

   Optional extras:
   ```bash
   uv sync --extra api    # API server (FastAPI/Uvicorn)
   uv sync --extra data   # XLSX + plot saving (openpyxl/matplotlib)
   uv sync --extra all    # everything
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Usage

### Running the Agent

```bash
# basic usage (auto-detects provider from available API keys)
uv run python -m coding_agent.main

# with streaming
uv run python -m coding_agent.main --stream

# with verbose output (shows reasoning)
uv run python -m coding_agent.main --verbose

# specify provider and model
uv run python -m coding_agent.main --provider anthropic --model claude-3-5-sonnet-20240620

# with debug logging
uv run python -m coding_agent.main --log-level DEBUG

# start API server
uv run python -m coding_agent.main --serve

# multi-agent mode (uses multi_agent config in config.yaml)
uv run python -m coding_agent.main --multi-agent

# multi-agent with selected workers
uv run python -m coding_agent.main --multi-agent --workers data_analyst
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--stream` | Enable streaming responses |
| `--verbose` | Show reasoning/thinking content |
| `--provider` | LLM provider (anthropic, openai, together, google) |
| `--model` | Model name override |
| `--log-level` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `--serve` | Start the API server instead of the REPL |
| `--host` | API server host (default: 127.0.0.1) |
| `--port` | API server port (default: 8000) |
| `--multi-agent` | Run supervisor + workers from `config.yaml` |
| `--workers` | Filter to specific workers (names from `config.yaml`) |
| `--visualize` | Generate Mermaid diagram of agent structure |

### Configuration

You can configure the agent via `config.yaml`:

```yaml
llm:
  provider: "anthropic"
  model: "claude-3-5-sonnet-20240620"
  temperature: 0.7
  max_tokens: 4096

multi_agent:
  supervisor:
    provider: "openai"
    model: "gpt-5"
  workers:
    data_analyst:
      provider: "together"
      model: "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8"
      tools: ["read", "list", "ask_user", "load_dataset", "dataset_info", "dataset_describe", "export_dataset"]
```

Or via environment variables:
- `LLM_PROVIDER`: Default provider
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TOGETHER_API_KEY`, `GOOGLE_API_KEY`: Provider API keys
- `TAVILY_API_KEY`: For web search functionality
- `CODING_AGENT_LOG_LEVEL`: Logging level

## Available Tools

### Core Tools

| Tool | Description |
|------|-------------|
| `calculator` | Basic arithmetic operations |
| `list_directory` | List files in a directory |
| `read_file` | Read file contents |
| `write_file` | Write content to files |
| `run_command` | Execute shell commands (with security restrictions) |
| `python_repl` | Execute Python code in a sandboxed REPL |
| `search_web` | Web search via Tavily API |
| `ask_user` | Request clarification from the user |

### Data Analysis Tools

Install `coding-agent[data]` (`uv sync --extra data`) for XLSX/plot support.

| Tool | Description |
|------|-------------|
| `load_dataset` | Load CSV/JSON/JSONL/XLSX into an in-memory dataset registry |
| `list_datasets` | List loaded datasets |
| `remove_dataset` | Remove a dataset from memory |
| `clear_datasets` | Clear all datasets from memory |
| `dataset_info` | Column types + missing counts |
| `dataset_head` | First N rows (markdown table) |
| `dataset_tail` | Last N rows (markdown table) |
| `dataset_sample` | Random sample of rows |
| `dataset_describe` | Descriptive stats for numeric columns |
| `dataset_value_counts` | Value counts for a column |
| `dataset_select_columns` | Project columns into a new dataset |
| `dataset_filter` | Row filtering with simple conditions |
| `dataset_sort` | Sort by one or more columns |
| `dataset_groupby_agg` | Group-by + aggregate (count/sum/mean/min/max) |
| `export_dataset` | Export dataset to CSV/JSONL/XLSX (requires confirmation) |
| `save_histogram_plot` | Save histogram plot (requires confirmation) |
| `save_scatter_plot` | Save scatter plot (requires confirmation) |
| `save_bar_plot` | Save bar plot of top value counts (requires confirmation) |

## Security Model

The agent implements defense-in-depth security:

1. **Path Validation**: All file operations are validated against allowed paths to prevent path traversal attacks
2. **Command Sanitization**: Shell commands are inspected for dangerous patterns (rm -rf, sudo, etc.)
3. **Python Code Inspection**: AST-based validation blocks dangerous imports and operations
4. **Restricted Builtins**: Python REPL runs with limited builtins and blocked modules

## Interrupt Pattern

The `ask_user` tool supports two modes:

1. **Interrupt Mode** (default): Agent raises `InterruptRequested`, control returns to caller
2. **Callback Mode**: Uses a callback function for synchronous input

```python
# example: handling interrupts
result = agent.run("help me with something")
while result.is_interrupted:
    user_response = input(f"Agent asks: {result.interrupt.question}\n> ")
    result = agent.resume(result.interrupt.tool_call_id, user_response)
```

## Development

### Project Structure

```
src/coding_agent/
├── agent.py           # main CodingAgent class with ReAct loop
├── main.py            # CLI entry point and REPL
├── stream_handler.py  # streaming response handling
├── logging.py         # logging configuration
├── types.py           # unified types (UnifiedMessage, ToolCall, etc.)
├── exceptions.py      # custom exception hierarchy
├── prompts.py         # system prompts and templates
├── clients/           # LLM provider implementations
│   ├── base.py        # BaseLLMClient abstract class
│   ├── factory.py     # client factory with registry
│   ├── openai_compat.py # shared base for OpenAI-compatible APIs
│   ├── openai.py      # OpenAI client
│   ├── together.py    # Together AI client
│   ├── anthropic.py   # Anthropic/Claude client
│   └── google.py      # Google Gemini client
├── tools/             # tool implementations
│   ├── base.py        # BaseTool abstract class
│   ├── ask_user.py    # human-in-the-loop tool
│   ├── calculator.py  # basic math operations
│   ├── data_analysis.py # dataset tools (csv/json/jsonl/xlsx, export, plots)
│   ├── filesystem.py  # file operations
│   ├── python_repl.py # Python code execution
│   ├── search.py      # web search
│   ├── security.py    # path/command/code validation
│   └── system.py      # shell command execution
├── multi_agent/       # supervisor/worker orchestration (optional)
│   ├── supervisor.py  # supervisor agent
│   ├── worker.py      # worker wrapper
│   ├── tools.py       # delegate/synthesize tools
│   └── workers/       # worker factories (coder/researcher/reviewer/context/data_analyst)
└── api/               # optional FastAPI server (install with --extra api)
└── utils/
    └── stream_parser.py # streaming response parsing
```

### Running Tests

```bash
# run all tests
uv run pytest

# run with verbose output
uv run pytest -v

# run specific test file
uv run pytest tests/test_agent.py
```

### Linting

```bash
uv run ruff check src/
uv run ruff format src/
```

## Adding a New Provider

1. Create a new client in `clients/` inheriting from `BaseLLMClient` or `OpenAICompatibleClient`
2. Register it in `clients/factory.py`:
   ```python
   _PROVIDER_REGISTRY["new_provider"] = {
       "class_path": "coding_agent.clients.new_provider.NewProviderClient",
       "api_key_env": "NEW_PROVIDER_API_KEY",
       "default_model": "default-model-name",
   }
   ```

## Adding a New Tool

1. Create a new tool in `tools/` inheriting from `BaseTool`
2. Implement the required properties and `execute()` method
3. Add it to the tools list in `main.py` (single-agent CLI) and/or to `_create_tools_from_names()` for multi-agent config support

```python
class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Description of what this tool does"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "First parameter"}
            },
            "required": ["param1"]
        }

    def execute(self, param1: str) -> str:
        return f"Result: {param1}"
```

