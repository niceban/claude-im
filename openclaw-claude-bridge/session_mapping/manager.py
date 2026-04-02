"""Session mapping manager with LRU eviction and idle timeout cleanup."""
import threading
import time
import uuid
from collections import OrderedDict
from typing import Optional, Dict

from session_mapping.backend import SessionBackend, InMemorySessionBackend
from config.settings import MAX_POOL_SIZE, IDLE_TIMEOUT


class SessionMappingManager:
    """Manages conversation_id to session_id mapping with LRU eviction."""

    def __init__(
        self,
        backend: Optional[SessionBackend] = None,
        max_pool_size: int = MAX_POOL_SIZE,
        idle_timeout: int = IDLE_TIMEOUT,
        adapter=None  # AdapterProcessManager instance for subprocess lifecycle
    ):
        self._backend = backend or InMemorySessionBackend()
        self._max_pool_size = max_pool_size
        self._idle_timeout = idle_timeout
        self._adapter = adapter  # For subprocess cleanup
        self._conversation_to_session: OrderedDict = OrderedDict()
        self._session_to_conversation: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

    def get_or_create_session(self, conversation_id: Optional[str] = None) -> tuple[str, str]:
        """
        Get existing session or create new one.

        Returns:
            tuple: (session_id, conversation_id)
        """
        with self._lock:
            if conversation_id and conversation_id in self._conversation_to_session:
                session_id = self._conversation_to_session[conversation_id]
                # Move to end (most recently used)
                self._conversation_to_session.move_to_end(conversation_id)
                self._backend.touch(session_id)
                return session_id, conversation_id

            # Need to create new session
            return self._create_new_session(conversation_id)

    def _create_new_session(self, conversation_id: Optional[str] = None) -> tuple[str, str]:
        """Create a new session with LRU eviction if needed."""
        # Evict LRU if at capacity
        while len(self._conversation_to_session) >= self._max_pool_size:
            self._evict_lru()

        # Generate IDs
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        # Create session in backend
        self._backend.create_session(session_id)

        # Store mapping
        self._conversation_to_session[conversation_id] = session_id
        self._session_to_conversation[session_id] = conversation_id
        self._conversation_to_session.move_to_end(conversation_id)

        return session_id, conversation_id

    def _evict_lru(self) -> None:
        """Evict least recently used session."""
        if not self._conversation_to_session:
            return

        # Get oldest (first) item
        conversation_id, session_id = self._conversation_to_session.popitem(last=False)
        del self._session_to_conversation[session_id]
        self._backend.destroy_session(session_id)
        # Also kill the subprocess via adapter (task 3.2.2)
        if self._adapter is not None:
            self._adapter.destroy_session(session_id)

    def destroy_session_by_conversation_id(self, conversation_id: str) -> bool:
        """Destroy a session by conversation ID."""
        with self._lock:
            if conversation_id not in self._conversation_to_session:
                return False

            session_id = self._conversation_to_session.pop(conversation_id)
            del self._session_to_conversation[session_id]
            self._backend.destroy_session(session_id)
            # Also kill the subprocess via adapter (task 3.2.1)
            if self._adapter is not None:
                self._adapter.destroy_session(session_id)
            return True

    def get_session_id(self, conversation_id: str) -> Optional[str]:
        """Get session_id for conversation_id."""
        return self._conversation_to_session.get(conversation_id)

    def is_session_alive(self, session_id: str) -> bool:
        """Check if session is alive."""
        return self._backend.is_session_alive(session_id)

    def cleanup_idle_sessions(self) -> int:
        """Clean up sessions idle longer than timeout. Returns count of cleaned sessions."""
        cleaned = 0
        now = time.time()

        with self._lock:
            to_remove = []
            for conversation_id, session_id in self._conversation_to_session.items():
                session = self._backend._sessions.get(session_id)
                if session and (now - session.get("last_used", 0)) > self._idle_timeout:
                    to_remove.append(conversation_id)

            for conversation_id in to_remove:
                session_id = self._conversation_to_session.pop(conversation_id)
                del self._session_to_conversation[session_id]
                self._backend.destroy_session(session_id)
                # Also kill subprocess via adapter (task 3.2.3)
                if self._adapter is not None:
                    self._adapter.destroy_session(session_id)
                cleaned += 1

        return cleaned

    def start_cleanup_thread(self) -> None:
        """Start background thread for idle cleanup."""
        if self._cleanup_thread is not None:
            return

        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def stop_cleanup_thread(self) -> None:
        """Stop background cleanup thread."""
        if self._cleanup_thread is None:
            return

        self._stop_cleanup.set()
        self._cleanup_thread.join(timeout=5)
        self._cleanup_thread = None

    def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while not self._stop_cleanup.is_set():
            time.sleep(60)  # Check every minute
            self.cleanup_idle_sessions()
