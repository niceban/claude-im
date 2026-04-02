"""Integration tests for Module 7."""
import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock
import sys

sys.path.insert(0, 'openclaw-claude-bridge')


class TestConversationIdMapping:
    """Tests 7.1.2: conversation_id → session_id mapping."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_conversation_id_creates_same_session(self, mock_controller_class):
        """Test same conversation_id returns same session."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()

        # Same conversation_id should map to same session
        session1 = manager.get_controller("conv-123")
        session2 = manager.get_controller("conv-123")

        assert session1 is session2

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_different_conversation_ids_different_sessions(self, mock_controller_class):
        """Test different conversation_ids create different sessions."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()

        session1 = manager.get_controller("conv-123")
        session2 = manager.get_controller("conv-456")

        assert session1 is not session2


class TestSendMessage:
    """Tests 7.1.1: HTTP request → claude_node response."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_send_message_returns_text_response(self, mock_controller_class):
        """Test send_message returns properly formatted response."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True

        mock_result = MagicMock()
        mock_result.result_text = "Hello, world!"
        mock_result.session_id = "test-session"
        mock_result.is_result_error = False
        mock_controller.send.return_value = mock_result

        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        controller = manager.get_controller("test-session")
        controller.start()  # Ensure _alive is set

        result = manager.send_message("Hello", "test-session")

        assert result["text"] == "Hello, world!"
        assert result["session_id"] == "test-session"

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_send_message_timeout_returns_error(self, mock_controller_class):
        """Test timeout returns error format."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller.send.return_value = None  # Timeout

        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        controller = manager.get_controller("test-session")
        controller.start()  # Ensure _alive is set

        result = manager.send_message("Hello", "test-session")

        assert "error" in result
        assert result["error"]["type"] == "timeout"


class TestMultiTurnDialogue:
    """Tests 7.1.3: Multi-turn dialogue."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_multiple_messages_same_session(self, mock_controller_class):
        """Test multiple messages in same conversation."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True

        # First message
        mock_result1 = MagicMock()
        mock_result1.result_text = "First response"
        mock_result1.session_id = "conv-123"
        mock_result1.is_result_error = False

        # Second message (same session)
        mock_result2 = MagicMock()
        mock_result2.result_text = "Second response"
        mock_result2.session_id = "conv-123"
        mock_result2.is_result_error = False

        mock_controller.send.side_effect = [mock_result1, mock_result2]
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        controller = manager.get_controller("conv-123")
        controller.start()  # Ensure _alive is set

        result1 = manager.send_message("First message", "conv-123")
        result2 = manager.send_message("Second message", "conv-123")

        assert result1["text"] == "First response"
        assert result2["text"] == "Second response"
        assert mock_controller.send.call_count == 2


class TestErrorRecovery:
    """Tests 7.1.4: Error recovery scenarios."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_controller_crash_recovery(self, mock_controller_class):
        """Test controller crash is detected and handled."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = False  # Process died
        mock_controller.start.return_value = False  # Can't restart
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        controller = manager.get_controller("test-session")

        # Controller should not be alive
        assert not controller.is_alive()

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_destroy_session_cleans_up(self, mock_controller_class):
        """Test destroy_session properly cleans up."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()

        # Create session
        controller = manager.get_controller("test-session")
        controller.start()

        # Destroy session
        manager.destroy_session("test-session")

        # Controller should be removed
        assert "test-session" not in manager._controllers
        mock_controller.stop.assert_called_once()

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_send_after_crash_returns_error(self, mock_controller_class):
        """Test sending message after crash returns error."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = False  # Process dead
        mock_controller.start.return_value = False  # Can't restart
        mock_controller.send.side_effect = RuntimeError("Controller not started")
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        controller = manager.get_controller("test-session")
        # Don't start - controller is dead

        # send_message should handle the error
        result = manager.send_message("Hello", "test-session")

        assert "error" in result
        assert result["error"]["type"] == "internal_error"


class TestSessionLifecycle:
    """Tests for session lifecycle management."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_session_created_on_first_request(self, mock_controller_class):
        """Test session is created on first message."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller.send.return_value = MagicMock(result_text="ok", is_result_error=False)
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()

        # Session should not exist yet
        assert len(manager._controllers) == 0

        # Get controller and manually start it (simulating what send_message would do)
        controller = manager.get_controller("conv-123")
        controller.start()  # Properly initialize _alive

        # Now send_message should work
        result = manager.send_message("Hello", "conv-123")

        assert "conv-123" in manager._controllers
        assert result["text"] == "ok"

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_idle_controller_marked_alive(self, mock_controller_class):
        """Test idle controller is properly tracked."""
        from claude_node_adapter.adapter import AdapterProcessManager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        controller = manager.get_controller("test-session")

        # Controller should be alive after start
        assert controller.is_alive() is True


class TestAdapterManagerSingleton:
    """Tests for AdapterProcessManager singleton behavior."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_get_process_manager_returns_singleton(self, mock_controller_class):
        """Test global manager is singleton."""
        from claude_node_adapter.adapter import get_process_manager

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        # Reset global
        import claude_node_adapter.adapter as adapter_module
        adapter_module._process_manager = None

        manager1 = get_process_manager()
        manager2 = get_process_manager()

        assert manager1 is manager2

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_shutdown_all_clears_managers(self, mock_controller_class):
        """Test shutdown_all destroys all managers."""
        from claude_node_adapter.adapter import get_process_manager, shutdown_all

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        # Reset and create manager with sessions
        import claude_node_adapter.adapter as adapter_module
        adapter_module._process_manager = None

        manager = get_process_manager()
        manager.get_controller("session-1")
        manager.get_controller("session-2")

        assert len(manager._controllers) == 2

        shutdown_all()

        # Should be cleared
        assert adapter_module._process_manager is None
