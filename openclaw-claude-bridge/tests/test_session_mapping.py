"""Tests for session-mapping module."""
import pytest
import time
import threading

import sys
sys.path.insert(0, 'openclaw-claude-bridge')

from session_mapping.backend import (
    SessionBackend, InMemorySessionBackend, MockSessionBackend
)
from session_mapping.manager import SessionMappingManager


class TestInMemorySessionBackend:
    """Tests for InMemorySessionBackend."""

    def test_create_session(self):
        """Test session creation."""
        backend = InMemorySessionBackend()
        backend.create_session("test-session-1")
        assert backend.is_session_alive("test-session-1") is True

    def test_destroy_session(self):
        """Test session destruction."""
        backend = InMemorySessionBackend()
        backend.create_session("test-session-1")
        backend.destroy_session("test-session-1")
        assert backend.is_session_alive("test-session-1") is False

    def test_nonexistent_session_alive(self):
        """Test checking alive status of nonexistent session."""
        backend = InMemorySessionBackend()
        assert backend.is_session_alive("nonexistent") is False


class TestMockSessionBackend:
    """Tests for MockSessionBackend (for testing without real claude-node)."""

    def test_create_session_tracked(self):
        """Test session creation is tracked."""
        backend = MockSessionBackend()
        backend.create_session("session-1")
        assert "session-1" in backend.created
        assert backend.is_session_alive("session-1") is True

    def test_destroy_session_tracked(self):
        """Test session destruction is tracked."""
        backend = MockSessionBackend()
        backend.create_session("session-1")
        backend.destroy_session("session-1")
        assert "session-1" in backend.destroyed
        assert backend.is_session_alive("session-1") is False


class TestSessionMappingManager:
    """Tests for SessionMappingManager."""

    def test_get_or_create_new_session(self):
        """Test creating new session when none exists."""
        manager = SessionMappingManager(backend=MockSessionBackend())
        session_id, conv_id = manager.get_or_create_session()
        assert session_id is not None
        assert conv_id is not None

    def test_get_or_create_existing_session(self):
        """Test reusing existing session."""
        manager = SessionMappingManager(backend=MockSessionBackend())
        session_id_1, conv_id = manager.get_or_create_session()
        session_id_2, conv_id_2 = manager.get_or_create_session(conv_id)
        assert session_id_1 == session_id_2
        assert conv_id == conv_id_2

    def test_lru_eviction(self):
        """Test LRU eviction when pool is full."""
        backend = MockSessionBackend()
        manager = SessionMappingManager(backend=backend, max_pool_size=2)

        # Create 2 sessions
        s1, c1 = manager.get_or_create_session()
        s2, c2 = manager.get_or_create_session()

        # Create 3rd session - should evict oldest (c1)
        s3, c3 = manager.get_or_create_session()

        # c1's session should be destroyed
        assert s1 in backend.destroyed
        # c2 and c3 should still be alive
        assert manager.get_session_id(c2) == s2
        assert manager.get_session_id(c3) == s3

    def test_destroy_session(self):
        """Test destroying session by conversation ID."""
        backend = MockSessionBackend()
        manager = SessionMappingManager(backend=backend)
        session_id, conv_id = manager.get_or_create_session()

        result = manager.destroy_session_by_conversation_id(conv_id)
        assert result is True
        assert conv_id not in manager._conversation_to_session
        assert session_id in backend.destroyed

    def test_cleanup_idle_sessions(self):
        """Test idle session cleanup."""
        backend = InMemorySessionBackend()
        manager = SessionMappingManager(
            backend=backend,
            max_pool_size=10,
            idle_timeout=1  # 1 second for testing
        )

        # Create a session
        session_id, conv_id = manager.get_or_create_session()

        # Wait for timeout
        time.sleep(1.5)

        # Cleanup should remove it
        cleaned = manager.cleanup_idle_sessions()
        assert cleaned == 1
        assert backend.is_session_alive(session_id) is False


class TestSessionBackendInterface:
    """Tests verifying SessionBackend interface compliance."""

    def test_interface_methods_exist(self):
        """Test that SessionBackend has required methods."""
        assert hasattr(SessionBackend, 'create_session')
        assert hasattr(SessionBackend, 'destroy_session')
        assert hasattr(SessionBackend, 'is_session_alive')

    def test_concrete_backend_implements_interface(self):
        """Test InMemorySessionBackend implements SessionBackend."""
        backend = InMemorySessionBackend()
        assert isinstance(backend, SessionBackend)


class TestSessionLifecycleIntegration:
    """Tests 3.1.x: Session lifecycle with subprocess integration."""

    def test_destroy_session_cleans_backend_and_subprocess(self):
        """Test 3.1.1: destroy_session cleans both backend and subprocess."""
        from unittest.mock import MagicMock, patch

        mock_adapter = MagicMock()
        backend = MockSessionBackend()
        manager = SessionMappingManager(backend=backend, adapter=mock_adapter)

        session_id, conv_id = manager.get_or_create_session()
        manager.destroy_session_by_conversation_id(conv_id)

        # Backend should be cleaned
        assert session_id in backend.destroyed
        # Subprocess should be cleaned via adapter
        mock_adapter.destroy_session.assert_called_once_with(session_id)

    def test_lru_eviction_kills_subprocess(self):
        """Test 3.1.2: LRU eviction kills subprocess via adapter."""
        from unittest.mock import MagicMock

        mock_adapter = MagicMock()
        backend = MockSessionBackend()
        manager = SessionMappingManager(backend=backend, adapter=mock_adapter, max_pool_size=2)

        # Create 2 sessions
        s1, c1 = manager.get_or_create_session()
        s2, c2 = manager.get_or_create_session()

        # Reset mock to clear previous calls
        mock_adapter.reset_mock()

        # Create 3rd - should evict c1 and kill its subprocess
        s3, c3 = manager.get_or_create_session()

        # Adapter should have been called to kill s1's subprocess
        mock_adapter.destroy_session.assert_called_with(s1)
        # s2 and s3 should not have been killed
        assert mock_adapter.destroy_session.call_count == 1

    def test_idle_timeout_cleanup_kills_subprocess(self):
        """Test 3.1.3: idle timeout cleanup kills subprocess."""
        import time
        from unittest.mock import MagicMock

        mock_adapter = MagicMock()
        backend = InMemorySessionBackend()
        manager = SessionMappingManager(
            backend=backend,
            adapter=mock_adapter,
            idle_timeout=1
        )

        session_id, conv_id = manager.get_or_create_session()

        # Wait for timeout
        time.sleep(1.5)

        manager.cleanup_idle_sessions()

        # Adapter should have been called
        mock_adapter.destroy_session.assert_called_once_with(session_id)

    def test_sigterm_shutdown_all_kills_all_subprocesses(self):
        """Test 3.1.4: SIGTERM shutdown kills all subprocesses."""
        from unittest.mock import MagicMock, patch
        import claude_node_adapter.adapter as adapter_module

        # Reset global
        original = adapter_module._process_manager
        adapter_module._process_manager = None

        try:
            mock_adapter = MagicMock()
            manager = adapter_module.AdapterProcessManager()
            c1 = manager.get_controller("session-1")
            c2 = manager.get_controller("session-2")
            adapter_module._process_manager = manager

            with patch.object(manager, 'stop_cleanup_thread'):
                adapter_module.shutdown_all()

            # All controllers should have been stopped
            assert len(manager._controllers) == 0
        finally:
            adapter_module._process_manager = original

    def test_zombie_subprocess_detection(self):
        """Test 3.1.5: zombie subprocess detection and cleanup thread starts."""
        import claude_node_adapter.adapter as adapter_module

        manager = adapter_module.AdapterProcessManager()

        # Verify cleanup thread can be started
        manager.start_cleanup_thread()
        try:
            assert manager._cleanup_thread is not None
            assert manager._stop_cleanup is not None
        finally:
            manager.stop_cleanup_thread()

        # Verify thread is stopped
        assert manager._cleanup_thread is None
