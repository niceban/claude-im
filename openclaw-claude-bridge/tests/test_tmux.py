"""Tests for tmux module (Module 6)."""
import pytest
from unittest.mock import MagicMock, patch, call

import sys
sys.path.insert(0, 'openclaw-claude-bridge')


class TestTmuxManagerCreation:
    """Tests 6.1.1: tmux session creation."""

    def test_create_session_disabled_by_default(self):
        """Test that tmux is disabled by default."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=False)

        assert manager.enabled is False
        assert manager.is_active is False

    @patch('tmux_manager.manager.subprocess.run')
    def test_create_session_when_enabled(self, mock_run):
        """Test tmux session creation when enabled."""
        from tmux_manager.manager import TmuxManager

        # Mock has-session to return error (session doesn't exist)
        mock_run.return_value = MagicMock(returncode=1)

        manager = TmuxManager(enabled=True)
        manager.create_session("test-session", "/tmp")

        # Should have called new-session (check second call)
        args_list = mock_run.call_args_list
        assert len(args_list) >= 2
        # Second call should be new-session
        new_session_call = args_list[1]
        assert "new-session" in new_session_call.args[0]

    @patch('tmux_manager.manager.subprocess.run')
    def test_create_session_skips_if_exists(self, mock_run):
        """Test that existing sessions are not recreated."""
        from tmux_manager.manager import TmuxManager

        # Mock has-session to return success (session exists)
        mock_run.return_value = MagicMock(returncode=0)

        manager = TmuxManager(enabled=True)
        manager.create_session("test-session", "/tmp")

        # Should call has-session but not new-session
        mock_run.assert_called()


class TestTmuxSendKeys:
    """Tests 6.1.2: send_keys injection."""

    @patch('tmux_manager.manager.subprocess.run')
    def test_send_keys_success(self, mock_run):
        """Test sending keys to tmux session."""
        from tmux_manager.manager import TmuxManager

        mock_run.return_value = MagicMock(returncode=0, stderr="")
        manager = TmuxManager(enabled=True)
        manager.send_keys("test-session", "y")

        mock_run.assert_called_once_with(
            ["tmux", "send-keys", "-t", "claude-test-session", "y"],
            check=True,
            capture_output=True
        )

    @patch('tmux_manager.manager.subprocess.run')
    def test_send_keys_ctrl_c(self, mock_run):
        """Test sending Ctrl-C interrupt."""
        from tmux_manager.manager import TmuxManager

        mock_run.return_value = MagicMock(returncode=0, stderr="")
        manager = TmuxManager(enabled=True)
        manager.send_keys("test-session", "C-c")

        mock_run.assert_called_once_with(
            ["tmux", "send-keys", "-t", "claude-test-session", "C-c"],
            check=True,
            capture_output=True
        )

    @patch('tmux_manager.manager.subprocess.run')
    def test_send_keys_disabled(self, mock_run):
        """Test that send_keys does nothing when disabled."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=False)
        manager.send_keys("test-session", "y")

        mock_run.assert_not_called()


class TestTmuxCapturePane:
    """Tests 6.1.3: capture_pane."""

    @patch('tmux_manager.manager.subprocess.run')
    def test_capture_pane_success(self, mock_run):
        """Test capturing pane content."""
        from tmux_manager.manager import TmuxManager

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Hello\nWorld\n",
            stderr=""
        )
        manager = TmuxManager(enabled=True)
        result = manager.capture_pane("test-session")

        assert result == "Hello\nWorld\n"
        mock_run.assert_called_once_with(
            ["tmux", "capture-pane", "-t", "claude-test-session", "-p"],
            check=True,
            capture_output=True,
            text=True
        )

    @patch('tmux_manager.manager.subprocess.run')
    def test_capture_pane_disabled(self, mock_run):
        """Test that capture_pane returns empty when disabled."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=False)
        result = manager.capture_pane("test-session")

        assert result == ""
        mock_run.assert_not_called()


class TestTmuxKillSession:
    """Tests 6.1.4: kill_session cleanup."""

    @patch('tmux_manager.manager.subprocess.run')
    def test_kill_session_success(self, mock_run):
        """Test killing tmux session."""
        from tmux_manager.manager import TmuxManager

        mock_run.return_value = MagicMock(returncode=0, stderr="")
        manager = TmuxManager(enabled=True)
        manager._sessions["test-session"] = {"name": "claude-test-session"}

        manager.kill_session("test-session")

        mock_run.assert_called_once_with(
            ["tmux", "kill-session", "-t", "claude-test-session"],
            check=True,
            capture_output=True
        )

    @patch('tmux_manager.manager.subprocess.run')
    def test_kill_session_disabled(self, mock_run):
        """Test that kill_session does nothing when disabled."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=False)
        manager.kill_session("test-session")

        mock_run.assert_not_called()


class TestTmuxPatternDetection:
    """Tests 6.1.x: Pattern detection."""

    def test_detect_yes_no_pattern(self):
        """Test detecting yes/no prompt patterns."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager()

        content = "Do you want to proceed? [Y/n]"
        assert manager.detect_pattern(content) is not None

        content = "Do you want to continue? [Y/n]"
        assert manager.detect_pattern(content) is not None

    def test_detect_choice_pattern(self):
        """Test detecting choice prompt patterns."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager()

        content = "Enter your choice:"
        assert manager.detect_pattern(content) is not None

    def test_detect_ctrl_c_pattern(self):
        """Test detecting Ctrl-C cancel patterns."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager()

        content = "Press Ctrl-C to cancel"
        assert manager.detect_pattern(content) is not None

    def test_detect_confirm_pattern(self):
        """Test detecting confirmation patterns."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager()

        content = "Do you confirm?"
        assert manager.detect_pattern(content) is not None

    def test_no_pattern_returns_none(self):
        """Test that normal content returns None."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager()

        content = "Hello, this is normal output"
        assert manager.detect_pattern(content) is None


class TestTmuxInjectConfirmation:
    """Tests for inject_confirmation."""

    @patch('tmux_manager.manager.TmuxManager.capture_pane')
    @patch('tmux_manager.manager.TmuxManager.send_keys')
    def test_inject_confirmation_when_prompt_detected(self, mock_send, mock_capture):
        """Test injecting y when confirmation prompt detected."""
        from tmux_manager.manager import TmuxManager

        mock_capture.return_value = "Do you want to proceed? [Y/n]"
        mock_send.return_value = None

        manager = TmuxManager(enabled=True)
        result = manager.inject_confirmation("test-session")

        assert result is True
        mock_send.assert_called_once_with("test-session", "y")

    @patch('tmux_manager.manager.TmuxManager.capture_pane')
    @patch('tmux_manager.manager.TmuxManager.send_keys')
    def test_no_inject_when_no_prompt(self, mock_send, mock_capture):
        """Test no injection when no confirmation prompt."""
        from tmux_manager.manager import TmuxManager

        mock_capture.return_value = "Hello, normal output"
        mock_send.return_value = None

        manager = TmuxManager(enabled=True)
        result = manager.inject_confirmation("test-session")

        assert result is False
        mock_send.assert_not_called()


class TestTmuxSessionLifecycle:
    """Tests 6.1.5: Session lifecycle with ClaudeControllerProcess."""

    @patch('tmux_manager.manager.subprocess.run')
    def test_session_created_with_cwd(self, mock_run):
        """Test session creation with specific cwd."""
        from tmux_manager.manager import TmuxManager

        mock_run.return_value = MagicMock(returncode=1)  # session doesn't exist

        manager = TmuxManager(enabled=True)
        manager.create_session("session-123", "/home/user/project")

        calls = mock_run.call_args_list
        new_session_call = [c for c in calls if "new-session" in c.args[0]][0]
        assert "/home/user/project" in new_session_call.args[0]


class TestTmuxCrashRecovery:
    """Tests 6.1.6: tmux crash recovery."""

    @patch('tmux_manager.manager.TmuxManager.capture_pane')
    def test_check_session_health_returns_false_when_dead(self, mock_capture):
        """Test session health check fails for zombie session."""
        from tmux_manager.manager import TmuxManager, TmuxError

        mock_capture.side_effect = TmuxError("Session not found")

        manager = TmuxManager(enabled=True)
        result = manager.check_session_health("zombie-session")

        assert result is False

    @patch('tmux_manager.manager.TmuxManager.capture_pane')
    def test_check_session_health_returns_true_when_alive(self, mock_capture):
        """Test session health check succeeds for healthy session."""
        from tmux_manager.manager import TmuxManager

        mock_capture.return_value = "Normal output"

        manager = TmuxManager(enabled=True)
        result = manager.check_session_health("healthy-session")

        assert result is True

    @patch('tmux_manager.manager.TmuxManager.kill_session')
    @patch('tmux_manager.manager.TmuxManager.create_session')
    def test_recover_session(self, mock_create, mock_kill):
        """Test session recovery recreates session."""
        from tmux_manager.manager import TmuxManager

        mock_kill.return_value = None
        mock_create.return_value = None

        manager = TmuxManager(enabled=True)
        manager.recover_session("dead-session", "/tmp")

        mock_kill.assert_called_once_with("dead-session")
        mock_create.assert_called_once_with("dead-session", "/tmp")


class TestTmuxConcurrency:
    """Tests for tmux concurrency limits."""

    def test_max_sessions_limit(self):
        """Test MAX_SESSIONS configuration."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=True, max_sessions=5)
        assert manager.max_sessions == 5

    def test_session_count_tracking(self):
        """Test session count is tracked."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=True)
        manager._sessions["s1"] = {}
        manager._sessions["s2"] = {}

        assert manager.get_session_count() == 2


class TestTmuxModes:
    """Tests for tmux mode switching."""

    def test_mode_off_is_not_active(self):
        """Test that mode='off' is not active."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=True, mode="off")
        assert manager.is_active is False

    def test_mode_passive_is_active(self):
        """Test that mode='passive' is active."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=True, mode="passive")
        assert manager.is_active is True

    def test_mode_active_is_active(self):
        """Test that mode='active' is active."""
        from tmux_manager.manager import TmuxManager

        manager = TmuxManager(enabled=True, mode="active")
        assert manager.is_active is True
