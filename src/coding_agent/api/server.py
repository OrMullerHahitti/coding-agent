"""FastAPI server for the coding agent."""

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AgentResponse,
    ConfirmationInfo,
    ConfirmRequest,
    InterruptInfo,
    ResumeRequest,
    RunRequest,
)
from .sessions import sessions
from .websocket import handle_websocket


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Coding Agent API",
        description="API for interacting with the coding agent",
        version="0.1.0",
    )

    # configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()


@app.post("/api/sessions", response_model=dict)
def create_session(
    provider: str = "openai",
    model: str | None = None,
    system_prompt: str = "You are a helpful coding assistant.",
) -> dict:
    """Create a new agent session."""
    session = sessions.create_session(
        provider=provider,
        model=model,
        system_prompt=system_prompt,
    )
    return {"session_id": session.id}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    """Delete a session."""
    if sessions.delete_session(session_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Session not found")


@app.post("/api/sessions/{session_id}/run", response_model=AgentResponse)
def run_agent(session_id: str, request: RunRequest) -> AgentResponse:
    """Run the agent with a user message."""
    session = sessions.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    try:
        result = session.agent.run(request.message, stream=False)
        return _convert_result(result)
    except Exception as e:
        return AgentResponse(state="error", error=str(e))


@app.post("/api/sessions/{session_id}/resume", response_model=AgentResponse)
def resume_agent(session_id: str, request: ResumeRequest) -> AgentResponse:
    """Resume after an interrupt (ask_user tool)."""
    session = sessions.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    try:
        result = session.agent.resume(request.tool_call_id, request.response)
        return _convert_result(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return AgentResponse(state="error", error=str(e))


@app.post("/api/sessions/{session_id}/confirm", response_model=AgentResponse)
def confirm_operation(session_id: str, request: ConfirmRequest) -> AgentResponse:
    """Confirm or reject a dangerous operation."""
    session = sessions.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    try:
        result = session.agent.resume_confirmation(
            request.tool_call_id, request.confirmed
        )
        return _convert_result(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return AgentResponse(state="error", error=str(e))


@app.get("/api/sessions/{session_id}/history")
def get_history(session_id: str) -> list[dict]:
    """Get conversation history for a session."""
    session = sessions.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return session.agent.get_history()


@app.post("/api/sessions/{session_id}/clear")
def clear_history(session_id: str) -> dict:
    """Clear conversation history for a session."""
    session = sessions.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    session.agent.clear_history()
    return {"status": "cleared"}


@app.websocket("/api/sessions/{session_id}/stream")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for streaming agent responses."""
    await handle_websocket(websocket, session_id)


def _convert_result(result) -> AgentResponse:
    """Convert AgentRunResult to API response."""
    state_map = {
        "COMPLETED": "completed",
        "INTERRUPTED": "interrupted",
        "AWAITING_CONFIRMATION": "awaiting_confirmation",
        "ERROR": "error",
    }

    response = AgentResponse(
        state=state_map.get(result.state.name, "error"),
        content=result.content,
        error=result.error,
    )

    if result.interrupt:
        response.interrupt = InterruptInfo(
            tool_name=result.interrupt.tool_name,
            tool_call_id=result.interrupt.tool_call_id,
            question=result.interrupt.question,
            context=result.interrupt.context,
        )

    if result.confirmation:
        response.confirmation = ConfirmationInfo(
            tool_name=result.confirmation.tool_name,
            tool_call_id=result.confirmation.tool_call_id,
            message=result.confirmation.message,
            operation=result.confirmation.operation,
            arguments=result.confirmation.arguments,
        )

    return response
