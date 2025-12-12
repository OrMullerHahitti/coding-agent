"""Session management for the API server."""

import time
import uuid
from dataclasses import dataclass, field

from ..agent import CodingAgent
from ..clients.factory import create_client
from ..tools import get_default_tools


@dataclass
class Session:
    """A user session with an agent instance."""

    id: str
    agent: CodingAgent
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Update last accessed time."""
        self.last_accessed = time.time()


class SessionManager:
    """Manages agent sessions."""

    def __init__(self, session_timeout: int = 3600):
        """Initialize session manager.

        Args:
            session_timeout: Session timeout in seconds (default 1 hour)
        """
        self._sessions: dict[str, Session] = {}
        self._timeout = session_timeout

    def create_session(
        self,
        provider: str = "openai",
        model: str | None = None,
        system_prompt: str = "You are a helpful coding assistant.",
    ) -> Session:
        """Create a new session with a fresh agent.

        Args:
            provider: LLM provider to use
            model: Model name (uses provider default if not specified)
            system_prompt: System prompt for the agent

        Returns:
            New session with agent
        """
        session_id = str(uuid.uuid4())
        client = create_client(provider, model=model)
        tools = get_default_tools()
        agent = CodingAgent(client=client, tools=tools, system_prompt=system_prompt)

        session = Session(id=session_id, agent=agent)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session if found and not expired, None otherwise
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None

        # check expiry
        if time.time() - session.last_accessed > self._timeout:
            del self._sessions[session_id]
            return None

        session.touch()
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if session was deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired sessions.

        Returns:
            Number of sessions removed
        """
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_accessed > self._timeout
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    @property
    def active_count(self) -> int:
        """Get number of active sessions."""
        return len(self._sessions)


# global session manager instance
sessions = SessionManager()
