# Getting Started

This guide will help you install, configure, and run the Coding Agent.

## Prerequisites

- **Python 3.12+** - the agent uses modern Python syntax
- **uv** - fast Python package manager ([install guide](https://docs.astral.sh/uv/getting-started/installation/))
- **API Key** - at least one LLM provider API key

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/coding-agent.git
cd coding-agent
```

### 2. Install Dependencies

```bash
uv sync
```

This installs all dependencies including the optional ones for different providers.

### 3. Set Up API Keys

Create a `.env` file or export environment variables:

```bash
# choose at least one provider
export ANTHROPIC_API_KEY="sk-ant-..."     # for Claude models
export OPENAI_API_KEY="sk-..."            # for GPT models
export TOGETHER_API_KEY="..."             # for Together AI (Llama, etc.)
export GOOGLE_API_KEY="..."               # for Gemini models

# optional: for web search
export TAVILY_API_KEY="tvly-..."
```

## Running the Agent

### Interactive CLI (REPL)

Start the interactive command-line interface:

```bash
# auto-detect provider from available API keys
uv run python -m coding_agent.main

# specify a provider
uv run python -m coding_agent.main --provider anthropic

# enable streaming output
uv run python -m coding_agent.main --stream

# verbose mode (shows reasoning)
uv run python -m coding_agent.main --stream --verbose

# specify a model
uv run python -m coding_agent.main --provider openai --model gpt-4-turbo
```

### API Server

Start the REST/WebSocket API server:

```bash
# default: http://127.0.0.1:8000
uv run python -m coding_agent.main --serve

# custom host and port
uv run python -m coding_agent.main --serve --host 0.0.0.0 --port 3000
```

## Your First Conversation

Once running, you'll see a prompt:

```
You:
```

Try some commands:

```
You: What files are in the current directory?
```

The agent will use the `list_directory` tool to list files.

```
You: Read the README.md file
```

The agent will use `read_file` to read and summarize the file.

```
You: Calculate 2^10
```

The agent will use the calculator tool.

### Handling Confirmations

When the agent wants to perform a potentially dangerous operation (write files, run commands, execute code), it will ask for confirmation:

```
[Confirm]: Write 42 characters to './output.txt' (y/n):
```

Type `y` to approve or `n` to cancel.

### Asking Questions

The agent can ask you questions when it needs clarification:

```
[Agent asks]: Should I create a new file or append to the existing one?
Your response: Create a new file
```

### Exiting

Type `exit` or `quit` to end the session, or press `Ctrl+C`.

## Quick Examples

### File Operations

```
You: List all Python files in the src directory
You: Read src/coding_agent/agent.py
You: Create a file called hello.py with a hello world function
```

### Code Execution

```
You: Run Python code to calculate the first 10 Fibonacci numbers
You: Execute 'ls -la' in the terminal
```

### Web Search

```
You: Search the web for "Python async best practices"
```

### Math

```
You: What is 1234 * 5678?
You: Divide 100 by 7
```

## Next Steps

- [Agent Architecture](./agent-architecture.md) - understand how the ReAct loop works
- [Tools Overview](./tools-overview.md) - learn about all available tools
- [CLI Reference](./cli-reference.md) - full command-line options
- [Configuration](./configuration.md) - customize the agent behavior
