"""WebSocket handler for streaming responses."""

import json

from fastapi import WebSocket, WebSocketDisconnect

from ..types import StreamChunk
from .sessions import sessions


async def handle_websocket(websocket: WebSocket, session_id: str) -> None:
    """Handle WebSocket connection for streaming.

    Protocol:
    - Client sends: {"type": "run", "message": "..."} to run agent
    - Client sends: {"type": "resume", "tool_call_id": "...", "response": "..."} to resume
    - Client sends: {"type": "confirm", "tool_call_id": "...", "confirmed": true/false}
    - Server sends: {"type": "chunk", "content": "..."} for content
    - Server sends: {"type": "reasoning", "content": "..."} for reasoning
    - Server sends: {"type": "tool_call", "name": "...", "args": {...}}
    - Server sends: {"type": "interrupt", ...} when interrupted
    - Server sends: {"type": "confirmation", ...} when awaiting confirmation
    - Server sends: {"type": "done", "content": "..."} when complete
    - Server sends: {"type": "error", "message": "..."} on error
    """
    await websocket.accept()

    session = sessions.get_session(session_id)
    if session is None:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "run":
                await _handle_run(websocket, session, data.get("message", ""))
            elif msg_type == "resume":
                await _handle_resume(
                    websocket, session,
                    data.get("tool_call_id"),
                    data.get("response"),
                )
            elif msg_type == "confirm":
                await _handle_confirm(
                    websocket, session,
                    data.get("tool_call_id"),
                    data.get("confirmed", False),
                )
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


async def _handle_run(websocket: WebSocket, session, message: str) -> None:
    """Handle run request with streaming."""
    try:
        # use non-streaming for now, streaming requires async generator support
        result = session.agent.run(message, stream=False)
        await _send_result(websocket, result)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})


async def _handle_resume(
    websocket: WebSocket, session, tool_call_id: str, response: str
) -> None:
    """Handle resume request."""
    try:
        result = session.agent.resume(tool_call_id, response)
        await _send_result(websocket, result)
    except ValueError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})


async def _handle_confirm(
    websocket: WebSocket, session, tool_call_id: str, confirmed: bool
) -> None:
    """Handle confirmation request."""
    try:
        result = session.agent.resume_confirmation(tool_call_id, confirmed)
        await _send_result(websocket, result)
    except ValueError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})


async def _send_result(websocket: WebSocket, result) -> None:
    """Send agent result over WebSocket."""
    if result.state.name == "COMPLETED":
        await websocket.send_json({
            "type": "done",
            "content": result.content,
        })
    elif result.state.name == "INTERRUPTED":
        await websocket.send_json({
            "type": "interrupt",
            "tool_name": result.interrupt.tool_name,
            "tool_call_id": result.interrupt.tool_call_id,
            "question": result.interrupt.question,
            "context": result.interrupt.context,
        })
    elif result.state.name == "AWAITING_CONFIRMATION":
        await websocket.send_json({
            "type": "confirmation",
            "tool_name": result.confirmation.tool_name,
            "tool_call_id": result.confirmation.tool_call_id,
            "message": result.confirmation.message,
            "operation": result.confirmation.operation,
            "arguments": result.confirmation.arguments,
        })
    elif result.state.name == "ERROR":
        await websocket.send_json({
            "type": "error",
            "message": result.error,
        })
