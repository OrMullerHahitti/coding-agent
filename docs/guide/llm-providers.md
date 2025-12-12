# LLM Providers

This guide explains the provider abstraction layer and how to work with different LLM providers.

## Supported Providers

| Provider | Models | Default Model |
|----------|--------|---------------|
| **Anthropic** | Claude 3.5/4 Opus, Sonnet, Haiku | `claude-sonnet-4-5-20250929` |
| **OpenAI** | GPT-4o, GPT-4 Turbo, o1 | `gpt-4o` |
| **Google** | Gemini 2.0/2.5 Flash, Pro | `gemini-2.0-flash` |
| **Together** | Llama 3.1, Mixtral, etc. | `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo` |

## Quick Start

```python
from coding_agent.clients import create_client

# auto-detect from environment
client = create_client("anthropic")

# specify model
client = create_client("openai", model="gpt-4-turbo")

# with configuration
client = create_client(
    "anthropic",
    model="claude-opus-4-5-20251101",
    client_config={"temperature": 0.7}
)
```

## Unified Types

All providers convert responses to unified types:

### UnifiedMessage

```python
@dataclass
class UnifiedMessage:
    role: MessageRole        # SYSTEM, USER, ASSISTANT, TOOL
    content: str | None      # text content
    reasoning_content: str | None  # thinking/reasoning output
    tool_calls: list[ToolCall]     # requested tool calls
    tool_call_id: str              # for tool response messages
    name: str                      # tool name for tool messages
```

### ToolCall

```python
@dataclass
class ToolCall:
    id: str                  # unique identifier
    name: str                # tool name
    arguments: dict[str, Any]  # parsed arguments
```

### UnifiedResponse

```python
@dataclass
class UnifiedResponse:
    message: UnifiedMessage
    finish_reason: FinishReason  # STOP, TOOL_USE, LENGTH, ERROR
    usage: UsageStats | None     # token counts
```

### StreamChunk

```python
@dataclass
class StreamChunk:
    delta_content: str | None
    delta_reasoning: str | None
    delta_tool_call: PartialToolCall | None
    finish_reason: FinishReason | None
```

## Provider Details

### Anthropic (Claude)

**Environment Variable:** `ANTHROPIC_API_KEY`

**Configuration Options:**
```python
client_config = {
    "temperature": 1.0,       # 0.0 - 1.0
    "top_p": 0.9,
    "top_k": 5,
    "max_tokens": 4096,
    "stop_sequences": [],

    # extended thinking (claude-opus-4-5, claude-sonnet-4-5)
    "thinking_enabled": True,
    "thinking_budget_tokens": 5000,  # min 1024

    # tool control
    "tool_choice": {"type": "auto"},  # or {"type": "tool", "name": "..."}
}
```

**Extended Thinking:**

Claude 3.5+ models support extended thinking mode where the model shows its reasoning process:

```python
client = create_client(
    "anthropic",
    model="claude-opus-4-5-20251101",
    client_config={
        "thinking_enabled": True,
        "thinking_budget_tokens": 10000,
    }
)

# with verbose mode, you'll see reasoning output
result = agent.run("Solve this complex problem", verbose=True)
```

**Message Format:**
- System prompt passed separately (not in messages)
- Tool calls use content blocks with `type: "tool_use"`
- Tool results in user messages with `type: "tool_result"`

---

### OpenAI (GPT)

**Environment Variable:** `OPENAI_API_KEY`

**Configuration Options:**
```python
client_config = {
    "temperature": 0.7,       # 0.0 - 2.0
    "top_p": 0.9,
    "max_tokens": 2048,
    "presence_penalty": 0.0,  # -2.0 to 2.0
    "frequency_penalty": 0.0, # -2.0 to 2.0
    "stop": [],

    # for o1 models
    "reasoning_effort": "medium",  # low, medium, high
}
```

**Available Models:**
- `gpt-4o` - latest multimodal model
- `gpt-4-turbo` - previous generation
- `gpt-4o-mini` - faster, cheaper
- `o1-preview` - reasoning model
- `o1-mini` - smaller reasoning model

**Message Format:**
- Standard OpenAI format with `role`, `content`, `tool_calls`
- Tool results use `role: "tool"` with `tool_call_id`

---

### Google (Gemini)

**Environment Variable:** `GOOGLE_API_KEY` or `GEMINI_API_KEY`

**Configuration Options:**
```python
client_config = {
    "temperature": 1.0,       # 0.0 - 2.0
    "top_p": 0.95,
    "top_k": 40,
    "max_tokens": 4096,
    "stop_sequences": [],

    # thinking features
    "thinking_budget": 10000,      # Flash: 0-24576, Pro: 128-32768
    "thinking_level": "high",      # "low" or "high" (Gemini 3 Pro)
    "include_thoughts": True,

    # function calling
    "function_calling_mode": "AUTO",  # AUTO, ANY, NONE
}
```

**Available Models:**
- `gemini-2.0-flash` - fast, efficient
- `gemini-2.5-pro-preview` - most capable
- `gemini-2.5-flash-preview` - balanced

**Thinking Budget Ranges:**
| Model | Min | Max |
|-------|-----|-----|
| Flash | 0 | 24576 |
| Pro | 128 | 32768 |

**Message Format:**
- Uses "parts" format for content
- Role names: `"user"` and `"model"` (not `"assistant"`)
- Tool calls use `function_call` in parts
- Tool results use `function_response` in parts

---

### Together AI

**Environment Variable:** `TOGETHER_API_KEY`

**Configuration Options:**
```python
client_config = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 50,
    "max_tokens": 4096,
    "repetition_penalty": 1.0,
    "stop": [],
}
```

**Available Models:**
- `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo` (default)
- `meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo`
- `mistralai/Mixtral-8x7B-Instruct-v0.1`
- `deepseek-ai/deepseek-coder-33b-instruct`

**DeepSeek Reasoning:**

DeepSeek models on Together use `<think>` tags for reasoning:

```python
client = create_client(
    "together",
    model="deepseek-ai/deepseek-r1-distill-llama-70b"
)

# reasoning appears in delta_reasoning during streaming
# or in reasoning_content in the final message
```

**Message Format:**
- OpenAI-compatible format
- Tool calls may come as dict or object (handled automatically)

## Generating Responses

### Non-Streaming

```python
from coding_agent.types import UnifiedMessage, MessageRole

messages = [
    UnifiedMessage(role=MessageRole.SYSTEM, content="You are helpful"),
    UnifiedMessage(role=MessageRole.USER, content="Hello!")
]

response = client.generate(messages, tools=None, stream=False)
print(response.message.content)
```

### Streaming

```python
messages = [...]
stream = client.generate(messages, tools=None, stream=True)

for chunk in stream:
    if chunk.delta_content:
        print(chunk.delta_content, end="", flush=True)
```

### With Tools

```python
from coding_agent.tools import get_default_tools

tools = get_default_tools()
response = client.generate(messages, tools=tools, stream=False)

if response.message.tool_calls:
    for call in response.message.tool_calls:
        print(f"Tool: {call.name}, Args: {call.arguments}")
```

## Provider Auto-Detection

The CLI auto-detects providers in this order:

1. `--provider` CLI argument
2. `llm.provider` in config.yaml
3. `LLM_PROVIDER` environment variable
4. First available API key:
   - `ANTHROPIC_API_KEY` → anthropic
   - `OPENAI_API_KEY` → openai
   - `TOGETHER_API_KEY` → together
   - `GOOGLE_API_KEY` → google

## Error Handling

All providers map errors to unified exceptions:

```python
from coding_agent.exceptions import (
    AuthenticationError,     # invalid API key
    RateLimitError,          # rate limit exceeded
    ContextLengthError,      # message too long
    ModelNotFoundError,      # invalid model
    ProviderUnavailableError,  # API down
    InvalidResponseError,    # parse error
)

try:
    response = client.generate(messages)
except AuthenticationError:
    print("Check your API key")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except ProviderUnavailableError:
    print("API is temporarily unavailable")
```

### Automatic Retry

The client includes automatic retry with exponential backoff for:
- `RateLimitError`
- `ProviderUnavailableError`

```python
# retry behavior (built-in)
# attempt 1: immediate
# attempt 2: wait 1s
# attempt 3: wait 2s
# attempt 4: wait 4s
# ...up to max_retries
```

## Message Format Comparison

### OpenAI/Together Format

```python
[
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {
        "role": "assistant",
        "content": "...",
        "tool_calls": [{
            "id": "call_123",
            "type": "function",
            "function": {"name": "tool", "arguments": "{}"}
        }]
    },
    {"role": "tool", "tool_call_id": "call_123", "content": "result"}
]
```

### Anthropic Format

```python
# system passed separately
system = "..."

messages = [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": [
        {"type": "text", "text": "..."},
        {"type": "tool_use", "id": "...", "name": "tool", "input": {}}
    ]},
    {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "...", "content": "result"}
    ]}
]
```

### Google Format

```python
# system in config
config.system_instruction = "..."

contents = [
    Content(role="user", parts=[Part.from_text("...")]),
    Content(role="model", parts=[
        Part.from_text("..."),
        Part.from_function_call(name="tool", args={})
    ]),
    Content(role="user", parts=[
        Part.from_function_response(name="tool", response={})
    ])
]
```

## Next Steps

- [Adding Providers](./adding-providers.md) - add new LLM providers
- [Configuration](./configuration.md) - configure provider settings
- [Streaming](./streaming.md) - understand streaming responses
