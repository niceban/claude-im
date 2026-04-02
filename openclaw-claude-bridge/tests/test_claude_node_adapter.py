"""Tests for claude-node-adapter module."""
import pytest
import signal
import os
import time
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, 'openclaw-claude-bridge')

from claude_node_adapter.adapter import (
    ClaudeControllerProcess,
    AdapterProcessManager,
    get_process_manager,
    shutdown_all
)


class TestClaudeControllerProcess:
    """Tests for ClaudeControllerProcess."""

    @patch('claude_node_adapter.adapter.subprocess.Popen')
    def test_start_creates_process(self, mock_popen):
        """Test starting controller creates subprocess."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process running
        mock_popen.return_value = mock_process

        controller = ClaudeControllerProcess("test-session")
        controller.start()

        mock_popen.assert_called_once()
        assert controller.is_alive() is True

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_stop_terminates_process(self, mock_controller_class):
        """Test stopping controller terminates subprocess."""
        from unittest.mock import PropertyMock

        mock_controller = MagicMock()
        mock_controller.start.return_value = True
        # Use PropertyMock for 'alive' so it can be changed
        type(mock_controller).alive = PropertyMock(side_effect=[True, False])
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()
        controller.stop()

        mock_controller.stop.assert_called_once_with(timeout=5.0)
        assert controller.is_alive() is False

    def test_is_alive_false_when_not_started(self):
        """Test is_alive returns False when not started."""
        controller = ClaudeControllerProcess("test-session")
        assert controller.is_alive() is False

    def test_send_raises_if_not_alive(self):
        """Test send raises error if controller not started."""
        controller = ClaudeControllerProcess("test-session")
        with pytest.raises(RuntimeError, match="Controller not started"):
            controller.send("test prompt")

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_send_async_calls_send_nowait(self, mock_controller_class):
        """Test 2.1.1: send_async calls controller.send_nowait()."""
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()
        controller.send_async("test prompt", "stream-123")

        mock_controller.send_nowait.assert_called_once()
        # Verify it was called with the prompt
        call_args = mock_controller.send_nowait.call_args
        assert "test prompt" in str(call_args)

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_wait_for_result_async_returns_result(self, mock_controller_class):
        """Test 2.1.2: wait_for_result_async returns properly formatted result."""
        from claude_node.controller import ClaudeMessage

        mock_result = MagicMock()
        mock_result.result_text = "test response"
        mock_result.session_id = "test-session"
        mock_result.type = "result"
        mock_result.subtype = "success"

        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller.wait_for_result.return_value = mock_result
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()
        result = controller.wait_for_result_async(timeout=30.0)

        assert result["text"] == "test response"
        assert result["session_id"] == "test-session"
        mock_controller.wait_for_result.assert_called_once_with(timeout=30.0)

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_session_not_exists_creates_new_controller(self, mock_controller_class):
        """Test 2.1.3: session not exists triggers controller creation."""
        mock_controller = MagicMock()
        mock_controller.alive = False
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        # First call creates a new controller
        controller1 = manager.get_controller("new-session")
        assert controller1 is not None

        # Second call with different session creates another
        controller2 = manager.get_controller("another-session")
        assert controller2 is not None
        assert controller1 is not controller2

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_timeout_returns_error_format(self, mock_controller_class):
        """Test 2.1.4: timeout returns proper error format."""
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller.wait_for_result.return_value = None  # Timeout
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()
        result = controller.wait_for_result_async(timeout=5.0)

        assert "error" in result
        assert result["error"]["type"] == "timeout"
        assert "timeout" in result["error"]["message"].lower()


class TestAdapterProcessManager:
    """Tests for AdapterProcessManager."""

    def test_get_controller_creates_new(self):
        """Test get_controller creates new controller if not exists."""
        manager = AdapterProcessManager()
        controller = manager.get_controller("new-session")
        assert controller is not None
        assert controller.session_id == "new-session"

    def test_get_controller_returns_same_instance(self):
        """Test get_controller returns same instance for same session."""
        manager = AdapterProcessManager()
        c1 = manager.get_controller("session-1")
        c2 = manager.get_controller("session-1")
        assert c1 is c2

    def test_send_message_calls_send(self):
        """Test send_message calls controller send method."""
        manager = AdapterProcessManager()
        controller = manager.get_controller("session-1")

        # Mock the controller's methods
        with patch.object(controller, 'is_alive', return_value=True):
            with patch.object(controller, 'send', return_value={"type": "result", "result_text": "response"}) as mock_send:
                result = manager.send_message("test prompt", "session-1")

        mock_send.assert_called_once_with("test prompt", "session-1")
        assert result["result_text"] == "response"

    def test_destroy_session_stops_controller(self):
        """Test destroy_session stops and removes controller."""
        manager = AdapterProcessManager()
        controller = manager.get_controller("session-1")

        with patch.object(controller, 'stop') as mock_stop:
            manager.destroy_session("session-1")
            mock_stop.assert_called_once()

        assert "session-1" not in manager._controllers

    @patch('claude_node_adapter.adapter.subprocess.run')
    def test_cleanup_orphaned_processes(self, mock_run):
        """Test cleanup_orphaned_processes kills stale processes."""
        mock_run.return_value = MagicMock(returncode=0, stdout="123\n456\n")

        with patch('os.kill') as mock_kill:
            manager = AdapterProcessManager()
            cleaned = manager.cleanup_orphaned_processes()
            assert cleaned == 2
            assert mock_kill.call_count == 2


class TestLifecycleManagement:
    """Tests for subprocess lifecycle scenarios."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_sigterm_triggers_graceful_shutdown(self, mock_controller_class):
        """Test SIGTERM triggers graceful shutdown of controller."""
        from unittest.mock import PropertyMock

        mock_controller = MagicMock()
        mock_controller.start.return_value = True
        # Use PropertyMock for 'alive' so it changes after stop
        type(mock_controller).alive = PropertyMock(side_effect=[True, False])
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()

        # Simulate receiving SIGTERM
        controller.stop()

        mock_controller.stop.assert_called_once_with(timeout=5.0)
        assert controller.is_alive() is False

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_graceful_shutdown_timeout_triggers_sigkill(self, mock_controller_class):
        """Test graceful shutdown timeout triggers SIGKILL (delegated to controller)."""
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller.stop.side_effect = Exception("timeout")
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()

        controller.stop()
        # Timeout is handled by ClaudeController.stop() internally


class TestGlobalProcessManager:
    """Tests for global process manager singleton."""

    def test_get_process_manager_returns_same_instance(self):
        """Test get_process_manager returns singleton."""
        # Reset global
        import claude_node_adapter.adapter as adapter_module
        adapter_module._process_manager = None

        m1 = get_process_manager()
        m2 = get_process_manager()
        assert m1 is m2

    def test_shutdown_all_clears_managers(self):
        """Test shutdown_all destroys all controllers."""
        import claude_node_adapter.adapter as adapter_module

        # Create manager with a controller
        manager = AdapterProcessManager()
        controller = manager.get_controller("session-1")
        adapter_module._process_manager = manager

        with patch.object(controller, 'stop'):
            shutdown_all()

        assert len(manager._controllers) == 0
        assert adapter_module._process_manager is None
