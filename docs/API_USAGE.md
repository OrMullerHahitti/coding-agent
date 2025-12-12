# API Usage Guide

The Coding Agent provides a REST API and WebSocket interface for programmatic access.

## Installation

```bash
# install with API dependencies
uv sync --extra api
```

## Starting the Server

```bash
# start on default port (8000)
uv run python -m coding_agent.main --serve

# specify port
uv run python -m coding_agent.main --serve --port 3000

# specify host (for external access)
uv run python -m coding_agent.main --serve --host 0.0.0.0 --port 8000
```

Output:
```
Starting API server at http://127.0.0.1:8000
API docs available at http://127.0.0.1:8000/docs
```

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## REST API Endpoints

### Create Session

Create a new agent session before sending messages.

```http
POST /api/sessions
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | string | "openai" | LLM provider |
| `model` | string | null | Model name |
| `system_prompt` | string | "You are a helpful coding assistant." | System prompt |

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/sessions?provider=openai"
```

### Send Message

Send a user message and get the agent's response.

```http
POST /api/sessions/{session_id}/run
```

**Request Body:**
```json
{
  "message": "Write a hello world function in Python",
  "stream": false
}
```

**Response:**
```json
{
  "state": "completed",
  "content": "Here's a simple hello world function:\n\n```python\ndef hello_world():\n    print('Hello, World!')\n```",
  "interrupt": null,
  "confirmation": null,
  "error": null
}
```

**States:**
| State | Description |
|-------|-------------|
| `completed` | Agent finished responding |
| `interrupted` | Agent needs user input (ask_user tool) |
| `awaiting_confirmation` | Agent needs confirmation for dangerous operation |
| `error` | An error occurred |

### Resume After Interrupt

When the agent asks a question (state: `interrupted`), resume with your answer.

```http
POST /api/sessions/{session_id}/resume
```

**Request Body:**
```json
{
  "tool_call_id": "call_abc123",
  "response": "I want to sort numbers"
}
```

**Response:** Same as `/run`

### Confirm Operation

When a dangerous operation needs confirmation (state: `awaiting_confirmation`).

```http
POST /api/sessions/{session_id}/confirm
```

**Request Body:**
```json
{
  "tool_call_id": "call_xyz789",
  "confirmed": true
}
```

**Response:** Same as `/run`

### Get History

Get the conversation history for a session.

```http
GET /api/sessions/{session_id}/history
```

**Response:**
```json
[
  {
    "role": "system",
    "content": "You are a helpful coding assistant."
  },
  {
    "role": "user",
    "content": "Hello"
  },
  {
    "role": "assistant",
    "content": "Hello! How can I help you today?"
  }
]
```

### Clear History

Clear conversation history (keeps system prompt).

```http
POST /api/sessions/{session_id}/clear
```

**Response:**
```json
{
  "status": "cleared"
}
```

### Delete Session

Delete a session and free resources.

```http
DELETE /api/sessions/{session_id}
```

**Response:**
```json
{
  "status": "deleted"
}
```

## WebSocket API

For real-time streaming responses, use the WebSocket endpoint.

### Connect

```
WS /api/sessions/{session_id}/stream
```

### Protocol

**Client sends:**

```json
// run agent
{"type": "run", "message": "Write a hello world function"}

// resume after interrupt
{"type": "resume", "tool_call_id": "call_abc123", "response": "numbers"}

// confirm operation
{"type": "confirm", "tool_call_id": "call_xyz789", "confirmed": true}
```

**Server sends:**

```json
// text content chunk
{"type": "chunk", "content": "Here's a"}

// reasoning content (if verbose)
{"type": "reasoning", "content": "I should write a simple function..."}

// tool call notification
{"type": "tool_call", "name": "write_file", "args": {"path": "hello.py"}}

// interrupt (needs user input)
{"type": "interrupt", "tool_name": "ask_user", "tool_call_id": "call_abc", "question": "What type?"}

// confirmation needed
{"type": "confirmation", "tool_name": "write_file", "tool_call_id": "call_xyz", "message": "Write 45 chars to 'hello.py'"}

// completed
{"type": "done", "content": "I've created the function for you."}

// error
{"type": "error", "message": "Session not found"}
```

### JavaScript Example

```javascript
const sessionId = "your-session-id";
const ws = new WebSocket(`ws://localhost:8000/api/sessions/${sessionId}/stream`);

ws.onopen = () => {
  // send a message
  ws.send(JSON.stringify({
    type: "run",
    message: "Write a fibonacci function"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case "chunk":
      // append to output
      console.log(data.content);
      break;

    case "confirmation":
      // show confirmation dialog
      const confirmed = confirm(data.message);
      ws.send(JSON.stringify({
        type: "confirm",
        tool_call_id: data.tool_call_id,
        confirmed: confirmed
      }));
      break;

    case "interrupt":
      // show input prompt
      const answer = prompt(data.question);
      ws.send(JSON.stringify({
        type: "resume",
        tool_call_id: data.tool_call_id,
        response: answer
      }));
      break;

    case "done":
      console.log("Complete:", data.content);
      break;

    case "error":
      console.error("Error:", data.message);
      break;
  }
};
```

### Python Example

```python
import asyncio
import websockets
import json

async def chat():
    session_id = "your-session-id"
    uri = f"ws://localhost:8000/api/sessions/{session_id}/stream"

    async with websockets.connect(uri) as ws:
        # send message
        await ws.send(json.dumps({
            "type": "run",
            "message": "Write a hello world function"
        }))

        # receive responses
        while True:
            response = await ws.recv()
            data = json.loads(response)

            if data["type"] == "chunk":
                print(data["content"], end="", flush=True)
            elif data["type"] == "done":
                print(f"\n\nComplete: {data['content']}")
                break
            elif data["type"] == "confirmation":
                confirm = input(f"\n{data['message']} (y/n): ")
                await ws.send(json.dumps({
                    "type": "confirm",
                    "tool_call_id": data["tool_call_id"],
                    "confirmed": confirm.lower() == "y"
                }))
            elif data["type"] == "error":
                print(f"Error: {data['message']}")
                break

asyncio.run(chat())
```

## Complete REST Example

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. create session
response = requests.post(f"{BASE_URL}/api/sessions", params={"provider": "openai"})
session_id = response.json()["session_id"]
print(f"Session: {session_id}")

# 2. send message
response = requests.post(
    f"{BASE_URL}/api/sessions/{session_id}/run",
    json={"message": "Write a file called test.py with print('hello')"}
)
result = response.json()

# 3. handle confirmation if needed
while result["state"] == "awaiting_confirmation":
    print(f"Confirm: {result['confirmation']['message']}")
    confirmed = input("(y/n): ").lower() == "y"

    response = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/confirm",
        json={
            "tool_call_id": result["confirmation"]["tool_call_id"],
            "confirmed": confirmed
        }
    )
    result = response.json()

# 4. handle interrupt if needed
while result["state"] == "interrupted":
    print(f"Question: {result['interrupt']['question']}")
    answer = input("Your answer: ")

    response = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/resume",
        json={
            "tool_call_id": result["interrupt"]["tool_call_id"],
            "response": answer
        }
    )
    result = response.json()

# 5. print final result
if result["state"] == "completed":
    print(f"Agent: {result['content']}")
elif result["state"] == "error":
    print(f"Error: {result['error']}")

# 6. cleanup
requests.delete(f"{BASE_URL}/api/sessions/{session_id}")
```

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Session not found or expired |
| 500 | Internal server error |

### Error Response

```json
{
  "detail": "Session not found or expired"
}
```

## Session Management

- Sessions expire after 1 hour of inactivity
- Each session maintains its own conversation history
- Sessions are stored in memory (lost on server restart)
- For production, consider adding Redis for session persistence

## CORS Configuration

By default, the server allows all origins. For production, configure CORS in `server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

## Rate Limiting

The API currently has no built-in rate limiting. For production, consider:
- Adding middleware rate limiting
- Using a reverse proxy (nginx, Cloudflare)
- Implementing per-session request limits
