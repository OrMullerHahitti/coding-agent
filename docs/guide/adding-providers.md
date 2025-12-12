# Adding New LLM Providers

This guide explains how to add support for new LLM providers to the Coding Agent.

## Overview

There are two paths to adding a new provider:

1. **OpenAI-Compatible API** - Extend `OpenAICompatibleClient` (recommended for most providers)
2. **Custom API** - Extend `BaseLLMClient` directly (for unique API formats)

## Path 1: OpenAI-Compatible Provider

Most LLM providers follow the OpenAI API format. Use this approach for providers like:
- Groq
- Fireworks AI
- Mistral AI
- Local LLMs (vLLM, llama.cpp server)

### Step 1: Create the Client Class

```python
# src/coding_agent/clients/my_provider.py

from contextlib import contextmanager
from typing import Any

from .openai_compat import OpenAICompatibleClient
from ..exceptions import (
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
)

# import provider SDK
from my_provider_sdk import MyProviderClient as SDK

class MyProviderClient(OpenAICompatibleClient):
    """client for My Provider API"""

    def _create_client(self, api_key: str | None) -> Any:
        """create the SDK client instance"""
        return SDK(api_key=api_key)

    def _get_supported_config_keys(self) -> set[str]:
        """return supported configuration parameters"""
        return {
            "temperature",
            "top_p",
            "top_k",
            "max_tokens",
            "stop",
            # add provider-specific options
        }

    def _get_default_api_args(self) -> dict[str, Any]:
        """return provider-specific default arguments"""
        return {
            "max_tokens": 4096,
            # add other defaults
        }

    @contextmanager
    def _handle_api_errors(self):
        """map provider errors to unified exceptions"""
        try:
            yield
        except SDK.AuthenticationError as e:
            raise AuthenticationError(str(e)) from e
        except SDK.RateLimitError as e:
            raise RateLimitError(str(e)) from e
        except SDK.APIConnectionError as e:
            raise ProviderUnavailableError(str(e)) from e
        except SDK.APIError as e:
            # re-raise as generic error
            raise
```

### Step 2: Handle Provider Quirks (Optional)

If the provider has quirks in streaming or tool calls, override specific methods:

```python
class MyProviderClient(OpenAICompatibleClient):
    # ... required methods ...

    def _parse_tool_call_from_delta(
        self,
        delta: Any,
        index: int,
        accumulated: dict[int, dict]
    ) -> PartialToolCall | None:
        """handle provider-specific tool call format"""
        # example: provider returns tool calls as dicts instead of objects
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            tc = delta.tool_calls[0]
            # handle both dict and object formats
            if isinstance(tc, dict):
                return PartialToolCall(
                    index=tc.get("index", index),
                    id=tc.get("id"),
                    name=tc.get("function", {}).get("name"),
                    arguments_delta=tc.get("function", {}).get("arguments")
                )
            else:
                # standard object format
                return super()._parse_tool_call_from_delta(delta, index, accumulated)
        return None
```

### Step 3: Register in Factory

```python
# src/coding_agent/clients/factory.py

_PROVIDER_REGISTRY = {
    # ... existing providers ...

    "my_provider": {
        "class_path": "coding_agent.clients.my_provider.MyProviderClient",
        "api_key_env": "MY_PROVIDER_API_KEY",
        "default_model": "my-model-name",
    },
}
```

### Step 4: Export from __init__.py

```python
# src/coding_agent/clients/__init__.py

from .my_provider import MyProviderClient

__all__ = [
    # ... existing exports ...
    "MyProviderClient",
]
```

## Path 2: Custom API Provider

For providers with unique API formats (like Anthropic or Google), extend `BaseLLMClient` directly.

### Step 1: Create the Client Class

```python
# src/coding_agent/clients/custom_provider.py

from typing import Any, Iterator
from contextlib import contextmanager

from .base import BaseLLMClient
from ..types import (
    UnifiedMessage,
    UnifiedResponse,
    StreamChunk,
    ToolCall,
    PartialToolCall,
    MessageRole,
    FinishReason,
    UsageStats,
)
from ..tools.base import BaseTool
from ..exceptions import (
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
    InvalidResponseError,
)

# import provider SDK
import custom_sdk

class CustomProviderClient(BaseLLMClient):
    """client for Custom Provider with unique API format"""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        client_config: dict[str, Any] | None = None,
    ):
        super().__init__(model, api_key, client_config)
        self._client = custom_sdk.Client(api_key=api_key)

    def generate(
        self,
        messages: list[UnifiedMessage],
        tools: list[BaseTool] | None = None,
        stream: bool = False,
    ) -> UnifiedResponse | Iterator[StreamChunk]:
        """generate a response from the LLM"""

        # convert to provider format
        provider_messages = self._convert_messages(messages)
        provider_tools = self._convert_tools(tools) if tools else None

        # extract system prompt if provider needs it separately
        system_prompt = None
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_prompt = msg.content
                break

        # build API arguments
        api_args = {
            "model": self.model,
            "messages": provider_messages,
            **self._get_config_args(),
        }

        if system_prompt:
            api_args["system"] = system_prompt

        if provider_tools:
            api_args["tools"] = provider_tools

        with self._handle_api_errors():
            if stream:
                return self._stream_response(api_args)
            else:
                response = self._client.generate(**api_args)
                return self._parse_response(response)

    def _convert_messages(self, messages: list[UnifiedMessage]) -> list[dict]:
        """convert unified messages to provider format"""
        result = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # skip if provider uses separate system parameter
                continue

            if msg.role == MessageRole.USER:
                result.append({
                    "role": "user",
                    "content": self._format_user_content(msg)
                })

            elif msg.role == MessageRole.ASSISTANT:
                result.append({
                    "role": "assistant",
                    "content": self._format_assistant_content(msg)
                })

            elif msg.role == MessageRole.TOOL:
                result.append({
                    "role": "tool_response",  # provider-specific
                    "tool_id": msg.tool_call_id,
                    "content": msg.content or ""
                })

        return result

    def _format_user_content(self, msg: UnifiedMessage) -> Any:
        """format user message content"""
        # provider-specific formatting
        return msg.content

    def _format_assistant_content(self, msg: UnifiedMessage) -> Any:
        """format assistant message with potential tool calls"""
        parts = []

        if msg.content:
            parts.append({"type": "text", "text": msg.content})

        for tc in msg.tool_calls:
            parts.append({
                "type": "tool_call",
                "id": tc.id,
                "name": tc.name,
                "arguments": tc.arguments
            })

        return parts if parts else msg.content

    def _convert_tools(self, tools: list[BaseTool]) -> list[dict]:
        """convert tools to provider format"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in tools
        ]

    def _parse_response(self, response: Any) -> UnifiedResponse:
        """parse provider response to unified format"""
        # extract content and tool calls
        content = None
        reasoning = None
        tool_calls = []

        for part in response.content:
            if part.type == "text":
                content = part.text
            elif part.type == "thinking":
                reasoning = part.text
            elif part.type == "tool_call":
                tool_calls.append(ToolCall(
                    id=part.id,
                    name=part.name,
                    arguments=part.arguments
                ))

        # determine finish reason
        if tool_calls:
            finish_reason = FinishReason.TOOL_USE
        elif response.stop_reason == "max_tokens":
            finish_reason = FinishReason.LENGTH
        else:
            finish_reason = FinishReason.STOP

        return UnifiedResponse(
            message=UnifiedMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                reasoning_content=reasoning,
                tool_calls=tool_calls,
            ),
            finish_reason=finish_reason,
            usage=UsageStats(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
            ) if response.usage else None
        )

    def _stream_response(self, api_args: dict) -> Iterator[StreamChunk]:
        """stream response chunks"""
        api_args["stream"] = True

        with self._handle_api_errors():
            stream = self._client.generate(**api_args)

            for event in stream:
                chunk = self._parse_stream_chunk(event)
                if chunk:
                    yield chunk

    def _parse_stream_chunk(self, event: Any) -> StreamChunk | None:
        """parse streaming event to unified chunk"""
        if event.type == "content_delta":
            return StreamChunk(
                delta_content=event.text,
                delta_reasoning=None,
                delta_tool_call=None,
                finish_reason=None,
            )
        elif event.type == "thinking_delta":
            return StreamChunk(
                delta_content=None,
                delta_reasoning=event.text,
                delta_tool_call=None,
                finish_reason=None,
            )
        elif event.type == "tool_call_delta":
            return StreamChunk(
                delta_content=None,
                delta_reasoning=None,
                delta_tool_call=PartialToolCall(
                    index=event.index,
                    id=event.id,
                    name=event.name,
                    arguments_delta=event.arguments_delta,
                ),
                finish_reason=None,
            )
        elif event.type == "done":
            return StreamChunk(
                delta_content=None,
                delta_reasoning=None,
                delta_tool_call=None,
                finish_reason=FinishReason.STOP,
            )

        return None

    def _get_config_args(self) -> dict[str, Any]:
        """filter config to supported keys"""
        supported = {"temperature", "top_p", "max_tokens"}
        return {k: v for k, v in self.client_config.items() if k in supported}

    @contextmanager
    def _handle_api_errors(self):
        """map provider errors to unified exceptions"""
        try:
            yield
        except custom_sdk.AuthError as e:
            raise AuthenticationError(str(e)) from e
        except custom_sdk.RateLimitError as e:
            raise RateLimitError(str(e)) from e
        except custom_sdk.ConnectionError as e:
            raise ProviderUnavailableError(str(e)) from e
```

### Step 2: Register and Export

Same as Path 1 - add to factory registry and `__init__.py`.

## Testing Your Provider

### Unit Tests

```python
# tests/test_my_provider.py

import pytest
from unittest.mock import Mock, patch
from coding_agent.clients.my_provider import MyProviderClient
from coding_agent.types import UnifiedMessage, MessageRole

@pytest.fixture
def client():
    with patch.dict("os.environ", {"MY_PROVIDER_API_KEY": "test-key"}):
        return MyProviderClient(model="test-model")

def test_convert_messages(client):
    messages = [
        UnifiedMessage(role=MessageRole.SYSTEM, content="Be helpful"),
        UnifiedMessage(role=MessageRole.USER, content="Hello"),
    ]
    converted = client._convert_messages(messages)

    assert len(converted) >= 1
    assert converted[-1]["role"] == "user"

def test_convert_tools(client):
    tool = Mock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.parameters = {"type": "object", "properties": {}}

    converted = client._convert_tools([tool])

    assert len(converted) == 1
    assert converted[0]["name"] == "test_tool"

def test_error_mapping(client):
    from coding_agent.exceptions import AuthenticationError
    import my_provider_sdk

    with patch.object(client._client, "generate") as mock:
        mock.side_effect = my_provider_sdk.AuthenticationError("Invalid key")

        with pytest.raises(AuthenticationError):
            client.generate([
                UnifiedMessage(role=MessageRole.USER, content="Hi")
            ])
```

### Integration Tests

```python
# tests/test_my_provider_integration.py

import pytest
import os

@pytest.mark.skipif(
    not os.getenv("MY_PROVIDER_API_KEY"),
    reason="MY_PROVIDER_API_KEY not set"
)
def test_real_generation():
    from coding_agent.clients import create_client

    client = create_client("my_provider")
    response = client.generate([
        UnifiedMessage(role=MessageRole.USER, content="Say hello")
    ])

    assert response.message.content
    assert "hello" in response.message.content.lower()
```

## Checklist

Before submitting a new provider:

- [ ] Client class implements all required methods
- [ ] Error handling maps to unified exceptions
- [ ] Streaming works correctly
- [ ] Tool calls are parsed properly
- [ ] Registered in factory with correct env var and default model
- [ ] Exported from `__init__.py`
- [ ] Unit tests pass
- [ ] Integration test with real API (optional but recommended)
- [ ] Documentation updated

## Example Providers

Study these implementations for reference:

| Provider | Path | Type |
|----------|------|------|
| OpenAI | `clients/openai.py` | OpenAI-compatible |
| Together | `clients/together.py` | OpenAI-compatible with quirks |
| Anthropic | `clients/anthropic.py` | Custom API |
| Google | `clients/google.py` | Custom API |

## Next Steps

- [LLM Providers](./llm-providers.md) - understand the provider abstraction
- [Streaming](./streaming.md) - learn about streaming implementation
- [Configuration](./configuration.md) - configure provider settings
