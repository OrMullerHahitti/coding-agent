# Creating Custom Tools

This guide explains how to create your own tools for the Coding Agent.

## The BaseTool Interface

All tools must inherit from `BaseTool` and implement four required members:

```python
from typing import Any
from coding_agent.tools.base import BaseTool

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        """unique tool identifier"""
        return "my_tool"

    @property
    def description(self) -> str:
        """human-readable description for the LLM"""
        return "Does something useful"

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON schema for tool parameters"""
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "First parameter"
                }
            },
            "required": ["param1"]
        }

    def execute(self, param1: str) -> str:
        """execute the tool and return result"""
        return f"Processed: {param1}"
```

## Complete Example: Weather Tool

Here's a complete example of a custom tool:

```python
from typing import Any
import requests
from coding_agent.tools.base import BaseTool

class WeatherTool(BaseTool):
    """tool to get current weather for a city"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Get the current weather for a specified city"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name (e.g., 'London', 'New York')"
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature units"
                }
            },
            "required": ["city"]
        }

    def execute(self, city: str, units: str = "celsius") -> str:
        """fetch weather from API"""
        try:
            # example API call (replace with real API)
            response = requests.get(
                f"https://api.weather.example/current",
                params={
                    "city": city,
                    "units": units,
                    "key": self.api_key
                }
            )
            data = response.json()
            return f"Weather in {city}: {data['temp']}° {units}, {data['condition']}"
        except Exception as e:
            return f"Error fetching weather: {e}"
```

## JSON Schema for Parameters

The `parameters` property must return a valid JSON schema. Here are common patterns:

### String Parameter

```python
"name": {
    "type": "string",
    "description": "The name to use"
}
```

### Enum (Choice) Parameter

```python
"format": {
    "type": "string",
    "enum": ["json", "csv", "xml"],
    "description": "Output format"
}
```

### Number Parameter

```python
"count": {
    "type": "integer",
    "description": "Number of items",
    "minimum": 1,
    "maximum": 100
}
```

### Boolean Parameter

```python
"verbose": {
    "type": "boolean",
    "description": "Enable verbose output"
}
```

### Array Parameter

```python
"tags": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of tags"
}
```

### Optional vs Required

Parameters listed in `"required"` are mandatory; others are optional:

```python
{
    "type": "object",
    "properties": {
        "required_param": {"type": "string", "description": "..."},
        "optional_param": {"type": "string", "description": "..."}
    },
    "required": ["required_param"]  # only required_param is mandatory
}
```

## Adding Confirmation for Dangerous Operations

For tools that perform potentially dangerous operations, add the confirmation pattern:

```python
class DangerousTool(BaseTool):
    # enable confirmation requirement
    REQUIRES_CONFIRMATION = True

    # message template (supports {kwarg} placeholders)
    CONFIRMATION_MESSAGE = "Perform dangerous action on '{target}'"

    # operation type for auto-approval pattern matching
    OPERATION_TYPE = "dangerous_action"

    # argument to check against auto-approval patterns
    CONFIRMATION_CHECK_ARG = "target"

    @property
    def name(self) -> str:
        return "dangerous_tool"

    @property
    def description(self) -> str:
        return "Performs a dangerous action that requires confirmation"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target of the action"
                }
            },
            "required": ["target"]
        }

    def execute(self, target: str) -> str:
        # this only runs after confirmation
        return f"Dangerous action performed on {target}"
```

### Confirmation Message Placeholders

The `CONFIRMATION_MESSAGE` template supports special placeholders:

| Placeholder | Description |
|-------------|-------------|
| `{arg_name}` | Value of any parameter |
| `{len_content}` | Length of `content` parameter |
| `{len_code}` | Length of `code` parameter |

Examples:
```python
CONFIRMATION_MESSAGE = "Write {len_content} characters to '{path}'"
CONFIRMATION_MESSAGE = "Execute Python code ({len_code} characters)"
CONFIRMATION_MESSAGE = "Run command: '{command}'"
```

## Creating an Interrupt Tool

For tools that need to pause and wait for user input:

```python
from coding_agent.tools.base import BaseTool
from coding_agent.exceptions import InterruptRequested

class ConfirmationTool(BaseTool):
    # mark as interrupt tool for agent identification
    INTERRUPT_TOOL = True

    @property
    def name(self) -> str:
        return "get_confirmation"

    @property
    def description(self) -> str:
        return "Ask user to confirm a decision"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Yes/no question to ask"
                }
            },
            "required": ["question"]
        }

    def execute(self, question: str, **kwargs) -> str:
        # get tool_call_id from kwargs (injected by agent)
        tool_call_id = kwargs.get("_tool_call_id", "unknown")

        # raise interrupt - agent will catch this
        raise InterruptRequested(
            tool_name=self.name,
            tool_call_id=tool_call_id,
            question=question,
            context={"type": "confirmation"}
        )
```

## Using Path Validation

For tools that work with files, use the `PathValidator`:

```python
from coding_agent.tools.base import BaseTool
from coding_agent.tools.security import get_path_validator, PathTraversalError

class SafeFileTool(BaseTool):
    @property
    def name(self) -> str:
        return "safe_file_tool"

    # ... other properties ...

    def execute(self, path: str) -> str:
        validator = get_path_validator()

        try:
            # validate and resolve path
            safe_path = validator.validate(path)

            # now safe to use safe_path
            with open(safe_path) as f:
                return f.read()

        except PathTraversalError as e:
            return f"Error: {e}"
```

## Using Command Validation

For tools that execute shell commands:

```python
from coding_agent.tools.base import BaseTool
from coding_agent.tools.security import get_command_runner, DisallowedCommandError

class SafeCommandTool(BaseTool):
    REQUIRES_CONFIRMATION = True
    CONFIRMATION_MESSAGE = "Run: '{command}'"
    OPERATION_TYPE = "execute"
    CONFIRMATION_CHECK_ARG = "command"

    @property
    def name(self) -> str:
        return "safe_command"

    # ... other properties ...

    def execute(self, command: str) -> str:
        runner = get_command_runner()

        try:
            stdout, stderr, returncode = runner.execute(command)
            output = stdout + stderr
            return output if output else f"Command exited with code {returncode}"

        except DisallowedCommandError as e:
            return f"Command blocked: {e.reason}"
```

## Registering Tools with the Agent

### Using Default Tools Plus Custom

```python
from coding_agent import CodingAgent
from coding_agent.clients import create_client
from coding_agent.tools import get_default_tools

# get default tools and add custom ones
tools = get_default_tools() + [
    WeatherTool(api_key="..."),
    MyCustomTool(),
]

agent = CodingAgent(
    client=create_client("anthropic"),
    tools=tools
)
```

### Using Only Custom Tools

```python
from coding_agent import CodingAgent
from coding_agent.clients import create_client

tools = [
    MyTool1(),
    MyTool2(),
]

agent = CodingAgent(
    client=create_client("openai"),
    tools=tools
)
```

## Error Handling Best Practices

1. **Return error strings, don't raise exceptions**
   ```python
   def execute(self, ...) -> str:
       try:
           result = do_something()
           return result
       except SomeError as e:
           return f"Error: {e}"  # return, don't raise
   ```

2. **Validate inputs early**
   ```python
   def execute(self, count: int) -> str:
       if count < 1 or count > 100:
           return "Error: count must be between 1 and 100"
       # proceed with valid count
   ```

3. **Handle missing optional parameters**
   ```python
   def execute(self, required: str, optional: str = None) -> str:
       if optional is None:
           optional = "default_value"
       # use optional safely
   ```

## Testing Custom Tools

```python
import pytest
from my_tools import WeatherTool

def test_weather_tool_schema():
    tool = WeatherTool(api_key="test")

    # verify schema is valid
    schema = tool.to_schema()
    assert schema["function"]["name"] == "get_weather"
    assert "city" in schema["function"]["parameters"]["properties"]

def test_weather_tool_execution(mocker):
    tool = WeatherTool(api_key="test")

    # mock the API call
    mocker.patch("requests.get", return_value=MockResponse({
        "temp": 20,
        "condition": "Sunny"
    }))

    result = tool.execute(city="London")
    assert "20°" in result
    assert "Sunny" in result
```

## Next Steps

- [Security](./security.md) - understand the security infrastructure
- [Human-in-the-Loop](./human-in-the-loop.md) - learn about interrupts and confirmations
- [Tools Overview](./tools-overview.md) - reference for built-in tools
