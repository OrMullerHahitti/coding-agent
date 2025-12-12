# Multi-Platform Implementation Plan

## Goal
Support the coding agent as:
1. **CLI tool** (current)
2. **Web app** (browser-based)
3. **Desktop app** (Electron/Tauri)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontends                            │
├─────────────────┬─────────────────┬─────────────────────────┤
│   CLI (Python)  │   Web (React)   │  Desktop (Tauri/Electron)│
└────────┬────────┴────────┬────────┴────────────┬────────────┘
         │                 │                      │
         ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent API Layer                          │
│              (FastAPI / WebSocket Server)                   │
├─────────────────────────────────────────────────────────────┤
│  POST /run          - start conversation                    │
│  POST /resume       - resume after interrupt                │
│  POST /confirm      - respond to confirmation               │
│  WS   /stream       - real-time streaming                   │
│  GET  /history      - get conversation history              │
│  POST /clear        - clear history                         │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Core Agent                              │
│                  (existing code)                            │
├─────────────────────────────────────────────────────────────┤
│  CodingAgent        - orchestration                         │
│  BaseLLMClient      - provider abstraction                  │
│  BaseTool           - tool interface                        │
│  StreamHandler      - streaming support                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: API Layer (Backend)

### 1.1 Create FastAPI Server

**File**: `src/coding_agent/api/server.py`

```python
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel

app = FastAPI()

class RunRequest(BaseModel):
    message: str
    stream: bool = False

class ResumeRequest(BaseModel):
    tool_call_id: str
    response: str

class ConfirmRequest(BaseModel):
    tool_call_id: str
    confirmed: bool
```

### 1.2 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/run` | POST | Send user message, get response |
| `/api/resume` | POST | Resume after interrupt (ask_user) |
| `/api/confirm` | POST | Confirm/reject dangerous operation |
| `/api/history` | GET | Get conversation history |
| `/api/clear` | POST | Clear conversation |
| `/api/stream` | WS | WebSocket for streaming responses |

### 1.3 Session Management

```python
# simple in-memory sessions (upgrade to Redis for production)
sessions: dict[str, CodingAgent] = {}

def get_or_create_session(session_id: str) -> CodingAgent:
    if session_id not in sessions:
        sessions[session_id] = create_agent()
    return sessions[session_id]
```

### 1.4 WebSocket Streaming

```python
@app.websocket("/api/stream/{session_id}")
async def stream_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    agent = get_or_create_session(session_id)

    while True:
        data = await websocket.receive_json()

        async for chunk in agent.run_async(data["message"], stream=True):
            await websocket.send_json({
                "type": "chunk",
                "content": chunk.delta_content,
                "reasoning": chunk.delta_reasoning,
            })

        await websocket.send_json({"type": "done"})
```

---

## Phase 2: Web Frontend

### 2.1 Tech Stack
- **Framework**: React + TypeScript
- **Styling**: Tailwind CSS
- **State**: Zustand or React Context
- **Markdown**: react-markdown + syntax highlighting

### 2.2 Project Structure

```
web/
├── src/
│   ├── components/
│   │   ├── ChatMessage.tsx
│   │   ├── ChatInput.tsx
│   │   ├── ConfirmationModal.tsx
│   │   ├── InterruptModal.tsx
│   │   ├── ToolExecution.tsx
│   │   └── StreamingText.tsx
│   ├── hooks/
│   │   ├── useAgent.ts
│   │   ├── useWebSocket.ts
│   │   └── useConfirmation.ts
│   ├── api/
│   │   └── client.ts
│   └── App.tsx
├── package.json
└── vite.config.ts
```

### 2.3 Key Components

**ChatMessage.tsx**
```tsx
interface Message {
  role: "user" | "assistant" | "tool";
  content: string;
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
}

function ChatMessage({ message }: { message: Message }) {
  return (
    <div className={`message ${message.role}`}>
      <Markdown>{message.content}</Markdown>
      {message.toolCalls?.map(tc => <ToolExecution key={tc.id} call={tc} />)}
    </div>
  );
}
```

**ConfirmationModal.tsx**
```tsx
function ConfirmationModal({ info, onConfirm, onReject }) {
  return (
    <Modal>
      <p>{info.message}</p>
      <div className="flex gap-2">
        <Button onClick={onReject}>Cancel</Button>
        <Button onClick={onConfirm} variant="danger">Confirm</Button>
      </div>
    </Modal>
  );
}
```

### 2.4 WebSocket Hook

```typescript
function useAgent(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState<PendingState | null>(null);
  const ws = useRef<WebSocket | null>(null);

  const send = (message: string) => {
    ws.current?.send(JSON.stringify({ message }));
  };

  const confirm = (toolCallId: string, confirmed: boolean) => {
    ws.current?.send(JSON.stringify({ type: "confirm", toolCallId, confirmed }));
  };

  return { messages, pending, send, confirm };
}
```

---

## Phase 3: Desktop App

### 3.1 Option A: Tauri (Recommended)
- **Pros**: Small bundle (~10MB), Rust backend, native performance
- **Cons**: Requires Rust toolchain

### 3.2 Option B: Electron
- **Pros**: Easier setup, same JS everywhere
- **Cons**: Large bundle (~150MB), higher memory usage

### 3.3 Tauri Structure

```
desktop/
├── src-tauri/
│   ├── src/
│   │   └── main.rs      # rust backend
│   ├── Cargo.toml
│   └── tauri.conf.json
├── src/                  # reuse web frontend
│   └── ...
├── package.json
└── vite.config.ts
```

### 3.4 Tauri Commands

```rust
// src-tauri/src/main.rs
#[tauri::command]
async fn run_agent(message: String, state: State<AgentState>) -> Result<Response, Error> {
    // call Python agent via PyO3 or HTTP
}

#[tauri::command]
async fn confirm_operation(tool_call_id: String, confirmed: bool) -> Result<Response, Error> {
    // handle confirmation
}
```

### 3.5 Python Integration Options

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **HTTP** | Bundle FastAPI server | Simple, works now | Extra process |
| **PyO3** | Embed Python in Rust | Single binary | Complex setup |
| **Sidecar** | Ship Python executable | Flexible | Large bundle |

**Recommended**: HTTP approach - run FastAPI server as sidecar process.

---

## Phase 4: Shared Code Strategy

### 4.1 Monorepo Structure

```
vanila-coding-agent/
├── src/coding_agent/     # python core (existing)
│   ├── agent.py
│   ├── api/              # NEW: FastAPI server
│   │   ├── server.py
│   │   ├── routes.py
│   │   └── schemas.py
│   └── ...
├── web/                  # NEW: web frontend
│   ├── src/
│   └── package.json
├── desktop/              # NEW: tauri app
│   ├── src-tauri/
│   ├── src/              # symlink to web/src
│   └── package.json
├── packages/             # NEW: shared types
│   └── types/
│       └── api.ts
└── pyproject.toml
```

### 4.2 Shared TypeScript Types

```typescript
// packages/types/api.ts
export interface AgentState {
  state: "completed" | "interrupted" | "awaiting_confirmation" | "error";
  content?: string;
  interrupt?: InterruptInfo;
  confirmation?: ConfirmationInfo;
}

export interface InterruptInfo {
  toolName: string;
  toolCallId: string;
  question: string;
}

export interface ConfirmationInfo {
  toolName: string;
  toolCallId: string;
  message: string;
  operation: string;
}
```

---

## Phase 5: Implementation Order

### Sprint 1: API Layer (1-2 weeks)
- [ ] Create FastAPI server with basic endpoints
- [ ] Add WebSocket streaming support
- [ ] Add session management
- [ ] Create OpenAPI schema
- [ ] Add CORS configuration
- [ ] Write API tests

### Sprint 2: Web Frontend (2-3 weeks)
- [ ] Set up React + Vite project
- [ ] Create chat UI components
- [ ] Implement WebSocket connection
- [ ] Add confirmation modal
- [ ] Add interrupt modal
- [ ] Implement streaming text display
- [ ] Add syntax highlighting for code
- [ ] Style with Tailwind

### Sprint 3: Desktop App (1-2 weeks)
- [ ] Set up Tauri project
- [ ] Reuse web frontend
- [ ] Add sidecar Python server
- [ ] Configure auto-start server
- [ ] Add system tray support
- [ ] Package for macOS/Windows/Linux

### Sprint 4: Polish (1 week)
- [ ] Error handling across all platforms
- [ ] Loading states and animations
- [ ] Keyboard shortcuts
- [ ] Settings/preferences UI
- [ ] Provider selection UI
- [ ] Dark/light theme

---

## File Changes Required

### New Files

| Path | Purpose |
|------|---------|
| `src/coding_agent/api/__init__.py` | API package |
| `src/coding_agent/api/server.py` | FastAPI app |
| `src/coding_agent/api/routes.py` | Route handlers |
| `src/coding_agent/api/schemas.py` | Pydantic models |
| `src/coding_agent/api/websocket.py` | WebSocket handler |
| `src/coding_agent/api/sessions.py` | Session management |
| `web/` | React frontend (new directory) |
| `desktop/` | Tauri app (new directory) |

### Modified Files

| Path | Changes |
|------|---------|
| `pyproject.toml` | Add fastapi, uvicorn, websockets deps |
| `src/coding_agent/main.py` | Add `--serve` flag to start API server |
| `src/coding_agent/agent.py` | Add `run_async()` for async streaming |

---

## CLI Compatibility

The CLI remains the default interface:

```bash
# existing CLI usage
uv run python -m coding_agent.main

# NEW: start API server
uv run python -m coding_agent.main --serve --port 8000

# NEW: start API server + open web UI
uv run python -m coding_agent.main --web
```

---

## Security Considerations

1. **API Authentication**: Add API key or JWT for production
2. **CORS**: Restrict origins in production
3. **Rate Limiting**: Prevent abuse
4. **Session Expiry**: Clean up old sessions
5. **Tool Sandboxing**: Same restrictions as CLI

---

## Dependencies to Add

```toml
# pyproject.toml
[project.optional-dependencies]
api = [
    "fastapi>=0.110.0",
    "uvicorn>=0.27.0",
    "websockets>=12.0",
    "python-multipart>=0.0.9",
]
```

Install with: `uv sync --extra api`
