# Coding Agent

A powerful, provider-agnostic coding agent capable of performing complex tasks using various LLM providers (Together AI, OpenAI, Anthropic, Google Gemini).

## Features

- **Multi-Provider Support**: Seamlessly switch between Together AI, OpenAI, Anthropic, and Google Gemini.
- **Tool Use**: Equipped with tools for file manipulation, system commands, Python REPL, and web search.
- **Streaming**: Real-time streaming responses.
- **Configuration**: Easy configuration via `config.yaml` or environment variables.
- **Agentic Workflow**: Uses a ReAct-like loop to reason, plan, and execute tasks.

## Tech Stack

- **Language**: Python 3.12+
- **Dependency Management**: `uv`
- **LLM Clients**: `together`, `openai`, `anthropic`, `google-generativeai`
- **Search**: `tavily-python`

## Prerequisites

- Python 3.12 or higher
- `uv` package manager (recommended)
- API keys for at least one provider (Together, OpenAI, Anthropic, or Google)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd coding-agent
    ```

2.  **Install dependencies:**
    ```bash
    uv sync
    # OR
    uv pip install -e .
    ```

3.  **Set up environment variables:**
    Copy `.env.example` to `.env` and fill in your API keys.
    ```bash
    cp .env.example .env
    ```

## Usage

Run the agent using the CLI:

```bash
uv run python -m coding_agent.main
```

### Options

- `--stream`: Enable streaming responses.
- `--visualize`: Generate a Mermaid graph of the agent structure.
- `--provider {together,openai,anthropic,google}`: Override the default provider.
- `--model <model_name>`: Override the default model.

### Configuration

You can configure the default provider and model in `config.yaml`:

```yaml
llm:
  provider: "together"
  model: "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
```

## Development

### Project Structure

- `src/coding_agent`: Main package source.
  - `agent.py`: Core agent logic.
  - `clients/`: LLM provider implementations.
  - `tools/`: Tool implementations.
  - `main.py`: CLI entry point.
- `tests/`: Test suite.

### Running Tests

```bash
uv run pytest
```
