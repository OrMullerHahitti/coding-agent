# Streaming Responses

This guide explains how streaming works in the Coding Agent.

## Overview

Streaming allows you to receive and display LLM responses incrementally instead of waiting for the complete response. This provides a better user experience for long responses.

```
Without streaming:          With streaming:
[waiting...]               H
[waiting...]               He
[waiting...]               Hel
[waiting...]               Hell
[waiting...]               Hello
"Hello, World!"            Hello,
                           Hello, W
                           Hello, Wo
                           Hello, Wor
                           Hello, Worl
                           Hello, World
                           Hello, World!
```

## Enabling Streaming

### CLI

```bash
# enable streaming
uv run python -m coding_agent.main --stream

# streaming with verbose mode (shows reasoning)
uv run python -m coding_agent.main --stream --verbose
```

### Programmatic

```python
from coding_agent import CodingAgent

# during agent run
result = agent.run("Hello!", stream=True, verbose=False)
```

## How Streaming Works

### Stream Flow

```
┌─────────────────────────────────────────────────┐
│           LLM Provider                          │
│   Returns Iterator[StreamChunk]                 │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│           StreamHandler                         │
│   - Accumulates content                         │
│   - Prints to console                           │
│   - Parses embedded tags                        │
│   - Builds final UnifiedMessage                 │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│           Agent Loop                            │
│   Uses final UnifiedMessage                     │
│   for history and tool execution                │
└─────────────────────────────────────────────────┘
```

### StreamChunk Structure

Each chunk from the LLM contains:

```python
@dataclass
class StreamChunk:
    delta_content: str | None       # new text content
    delta_reasoning: str | None     # new reasoning content
    delta_tool_call: PartialToolCall | None  # tool call update
    finish_reason: FinishReason | None  # set on final chunk
```

### PartialToolCall Structure

Tool calls arrive incrementally:

```python
@dataclass
class PartialToolCall:
    index: int          # which tool call (0, 1, 2, ...)
    id: str | None      # call ID (first chunk only)
    name: str | None    # tool name (first chunk only)
    arguments_delta: str | None  # JSON fragment
```

## StreamHandler

The `StreamHandler` class processes streaming responses:

```python
from coding_agent.stream_handler import StreamHandler

handler = StreamHandler(verbose=True)
message = handler.process_stream(stream_iterator)
```

### What It Does

1. **Accumulates Content** - Combines `delta_content` chunks into full content
2. **Accumulates Reasoning** - Combines `delta_reasoning` for verbose mode
3. **Builds Tool Calls** - Reassembles partial tool calls into complete `ToolCall` objects
4. **Prints to Console** - Shows content in real-time with appropriate prefixes
5. **Returns UnifiedMessage** - Final message for conversation history

### Output Formatting

```
# regular content
Agent: Hello! I'll help you with that...

# verbose mode shows reasoning
[Reasoning]: Let me think about this step by step...
Agent: Based on my analysis...

# tool calls shown in verbose mode
[Tool Call]: read_file(path="./README.md")
```

## StreamReasoningParser

Some providers embed reasoning in special tags within the content stream. The `StreamReasoningParser` handles this:

```python
from coding_agent.utils.stream_parser import StreamReasoningParser

parser = StreamReasoningParser()

# process chunks
for chunk in stream:
    result = parser.process_chunk(chunk.delta_content)
    if result.reasoning:
        print(f"[Thinking] {result.reasoning}")
    if result.content:
        print(result.content, end="")
```

### Supported Tag Formats

```
# DeepSeek-style thinking
<think>Let me consider this...</think>

# Generic reasoning tags
<reasoning>Step 1: First I'll...</reasoning>
```

## Implementing Streaming in Custom Code

### Basic Streaming

```python
from coding_agent.clients import create_client
from coding_agent.types import UnifiedMessage, MessageRole

client = create_client("anthropic")

messages = [
    UnifiedMessage(role=MessageRole.USER, content="Write a poem")
]

# get stream iterator
stream = client.generate(messages, stream=True)

# process chunks
full_content = ""
for chunk in stream:
    if chunk.delta_content:
        print(chunk.delta_content, end="", flush=True)
        full_content += chunk.delta_content

print()  # newline at end
```

### Handling Tool Calls in Streams

```python
from coding_agent.types import ToolCall
import json

accumulated_tool_calls: dict[int, dict] = {}

for chunk in stream:
    if chunk.delta_tool_call:
        tc = chunk.delta_tool_call
        index = tc.index

        # initialize if new tool call
        if index not in accumulated_tool_calls:
            accumulated_tool_calls[index] = {
                "id": tc.id,
                "name": tc.name,
                "arguments": ""
            }

        # accumulate ID and name (first chunk)
        if tc.id:
            accumulated_tool_calls[index]["id"] = tc.id
        if tc.name:
            accumulated_tool_calls[index]["name"] = tc.name

        # accumulate arguments JSON
        if tc.arguments_delta:
            accumulated_tool_calls[index]["arguments"] += tc.arguments_delta

# after stream ends, parse tool calls
tool_calls = []
for data in accumulated_tool_calls.values():
    tool_calls.append(ToolCall(
        id=data["id"],
        name=data["name"],
        arguments=json.loads(data["arguments"])
    ))
```

### Using StreamHandler

```python
from coding_agent.stream_handler import StreamHandler

handler = StreamHandler(verbose=True)

# process_stream handles all accumulation and printing
message = handler.process_stream(stream)

# message is complete UnifiedMessage with:
# - content
# - reasoning_content (if verbose)
# - tool_calls (parsed and ready)
```

## WebSocket Streaming

The API server supports streaming over WebSocket:

```python
import websockets
import json

async def stream_chat():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        # send message
        await ws.send(json.dumps({
            "message": "Write a story",
            "stream": True
        }))

        # receive chunks
        async for message in ws:
            data = json.loads(message)

            if data["type"] == "chunk":
                print(data["content"], end="", flush=True)
            elif data["type"] == "tool_call":
                print(f"\n[Tool: {data['name']}]")
            elif data["type"] == "done":
                print("\n--- Done ---")
                break
            elif data["type"] == "error":
                print(f"\nError: {data['message']}")
                break
```

## Provider-Specific Notes

### Anthropic

- Streams using Server-Sent Events
- Content arrives in `content_block_delta` events
- Thinking content in separate `thinking` blocks
- Tool calls announced via `content_block_start`

### OpenAI

- Standard SSE streaming
- Tool calls include `index` for ordering
- Arguments arrive as JSON fragments

### Google

- Uses parts-based streaming
- Function calls in separate parts
- Thinking content via `thoughts` part

### Together

- OpenAI-compatible streaming
- Some models return tool calls as dicts (handled automatically)
- DeepSeek models use `<think>` tags in content

## Performance Considerations

### Buffer Size

The default print uses unbuffered output (`flush=True`). For high-throughput scenarios, consider buffering:

```python
import sys

buffer = []
for chunk in stream:
    if chunk.delta_content:
        buffer.append(chunk.delta_content)
        if len(buffer) >= 10:  # flush every 10 chunks
            sys.stdout.write("".join(buffer))
            sys.stdout.flush()
            buffer = []

# flush remaining
if buffer:
    sys.stdout.write("".join(buffer))
    sys.stdout.flush()
```

### Memory

For very long responses, the accumulator grows linearly. This is usually fine, but for extreme cases consider:

```python
# process chunks without full accumulation
for chunk in stream:
    if chunk.delta_content:
        # write to file or database instead of memory
        output_file.write(chunk.delta_content)
```

## Debugging Streams

### Verbose Mode

Enable verbose mode to see all stream activity:

```bash
uv run python -m coding_agent.main --stream --verbose --log-level DEBUG
```

### Log Stream Chunks

```python
import logging
logging.basicConfig(level=logging.DEBUG)

for chunk in stream:
    logging.debug(f"Chunk: {chunk}")
    # process chunk...
```

## Next Steps

- [LLM Providers](./llm-providers.md) - provider-specific streaming details
- [CLI Reference](./cli-reference.md) - streaming CLI options
- [Human-in-the-Loop](./human-in-the-loop.md) - interrupts during streaming
