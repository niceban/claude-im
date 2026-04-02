"""SessionBackend abstract interface and in-memory implementation."""
from abc import ABC, abstractmethod
from typing import Dict, Optional
import time


class SessionBackend(ABC):
    """Abstract interface for session lifecycle operations."""

    @abstractmethod
    def create_session(self, session_id: str) -> None:
        """Create a new session."""
        pass

    @abstractmethod
    def destroy_session(self, session_id: str) -> None:
        """Destroy an existing session."""
        pass

    @abstractmethod
    def is_session_alive(self, session_id: str) -> bool:
        """Check if a session is alive."""
        pass


class InMemorySessionBackend(SessionBackend):
    """In-memory implementation of SessionBackend for MVP."""

    def __init__(self):
        self._sessions: Dict[str, dict] = {}

    def create_session(self, session_id: str) -> None:
        self._sessions[session_id] = {
            "created_at": time.time(),
            "last_used": time.time(),
            "alive": True
        }

    def destroy_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["alive"] = False

    def is_session_alive(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        return session.get("alive", False)

    def touch(self, session_id: str) -> None:
        """Update last_used timestamp."""
        if session_id in self._sessions:
            self._sessions[session_id]["last_used"] = time.time()


class MockSessionBackend(SessionBackend):
    """Mock implementation for testing without real claude-node."""

    def __init__(self):
        self.created = []
        self.destroyed = []
        self.alive_checks: Dict[str, bool] = {}

    def create_session(self, session_id: str) -> None:
        self.created.append(session_id)
        self.alive_checks[session_id] = True

    def destroy_session(self, session_id: str) -> None:
        self.destroyed.append(session_id)
        self.alive_checks[session_id] = False

    def is_session_alive(self, session_id: str) -> bool:
        return self.alive_checks.get(session_id, False)

    def touch(self, session_id: str) -> None:
        """Mock touch - no-op for testing."""
        pass
