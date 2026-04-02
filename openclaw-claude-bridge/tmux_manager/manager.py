"""TmuxManager for interactive session management."""
import os
import re
import subprocess
from typing import Optional, Dict, Any

from config.settings import (
    TMUX_ENABLED,
    TMUX_MODE,
    MAX_TMUX_SESSIONS,
    TMUX_SESSION_TIMEOUT,
)


class TmuxError(Exception):
    """Tmux operation error."""
    pass


class TmuxManager:
    """Manages tmux sessions for interactive command injection.

    Tmux is used as a "backdoor" for 1% of cases where interactive
    confirmation is needed (e.g., "Do you want to proceed? [Y/n]").

    Default mode is OFF - direct mode is used for 99% of requests.
    """

    def __init__(
        self,
        enabled: bool = TMUX_ENABLED,
        mode: str = TMUX_MODE,
        max_sessions: int = MAX_TMUX_SESSIONS,
        session_timeout: int = TMUX_SESSION_TIMEOUT,
    ):
        self.enabled = enabled
        self.mode = mode  # "off", "passive", "active"
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self._sessions: Dict[str, dict] = {}  # session_id -> metadata

    @property
    def is_active(self) -> bool:
        """Check if tmux mode is active (not off)."""
        return self.enabled and self.mode != "off"

    def create_session(self, session_id: str, cwd: str = "/tmp") -> None:
        """Create a new tmux session.

        Args:
            session_id: Unique session identifier
            cwd: Working directory for the session

        Raises:
            TmuxError: If session creation fails
        """
        if not self.enabled:
            return

        session_name = f"claude-{session_id}"

        try:
            # Check if session already exists
            result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Session already exists
                return

            # Create new detached session
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name, "-c", cwd],
                check=True,
                capture_output=True,
            )

            self._sessions[session_id] = {
                "name": session_name,
                "cwd": cwd,
                "created_at": None,  # Could track time here
            }

        except subprocess.CalledProcessError as e:
            raise TmuxError(f"Failed to create tmux session: {e}")

    def send_keys(self, session_id: str, keys: str) -> None:
        """Send key presses to a tmux session.

        Args:
            session_id: Session identifier
            keys: Keys to send (e.g., "y", "C-c" for Ctrl-C)

        Raises:
            TmuxError: If send fails
        """
        if not self.enabled:
            return

        session_name = f"claude-{session_id}"

        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, keys],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise TmuxError(f"Failed to send keys to tmux session: {e}")

    def capture_pane(self, session_id: str) -> str:
        """Capture the visible pane content from a tmux session.

        Args:
            session_id: Session identifier

        Returns:
            The visible pane content as a string

        Raises:
            TmuxError: If capture fails
        """
        if not self.enabled:
            return ""

        session_name = f"claude-{session_id}"

        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session_name, "-p"],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise TmuxError(f"Failed to capture tmux pane: {e}")

    def kill_session(self, session_id: str) -> None:
        """Kill a tmux session.

        Args:
            session_id: Session identifier

        Raises:
            TmuxError: If kill fails
        """
        if not self.enabled:
            return

        session_name = f"claude-{session_id}"

        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                check=True,
                capture_output=True,
            )
            if session_id in self._sessions:
                del self._sessions[session_id]
        except subprocess.CalledProcessError as e:
            # Session might already be dead, which is fine
            if "no server" not in e.stderr.lower():
                raise TmuxError(f"Failed to kill tmux session: {e}")

    def detect_pattern(self, pane_content: str) -> Optional[str]:
        """Detect interactive prompt patterns in pane content.

        Args:
            pane_content: Content from capture_pane

        Returns:
            The matched pattern string, or None if no match
        """
        patterns = [
            r"Do you want to proceed\? \[Y/n\]",
            r"Do you want to continue\? \[Y/n\]",
            r"Enter your choice:",
            r"Press Ctrl-C to cancel",
            r"Do you confirm\?",
            r"Shall I proceed\?",
            r"\(y/n\)",
            r"\[Y/n\]\s*$",
        ]

        for pattern in patterns:
            if re.search(pattern, pane_content, re.IGNORECASE):
                return pattern

        return None

    def inject_confirmation(self, session_id: str) -> bool:
        """Inject 'y' confirmation if a confirmation prompt is detected.

        Args:
            session_id: Session identifier

        Returns:
            True if confirmation was injected, False otherwise
        """
        if not self.enabled:
            return False

        pane = self.capture_pane(session_id)
        if self.detect_pattern(pane):
            self.send_keys(session_id, "y")
            return True
        return False

    def inject_interrupt(self, session_id: str) -> bool:
        """Inject Ctrl-C interrupt.

        Args:
            session_id: Session identifier

        Returns:
            True if interrupt was injected
        """
        if not self.enabled:
            return False

        self.send_keys(session_id, "C-c")
        return True

    def check_session_health(self, session_id: str) -> bool:
        """Check if a session is healthy (not zombie).

        Args:
            session_id: Session identifier

        Returns:
            True if session is healthy, False otherwise
        """
        if not self.enabled:
            return True

        try:
            self.capture_pane(session_id)
            return True
        except TmuxError:
            return False

    def recover_session(self, session_id: str, cwd: str = "/tmp") -> None:
        """Recover or recreate a session.

        Args:
            session_id: Session identifier
            cwd: Working directory
        """
        if not self.enabled:
            return

        try:
            self.kill_session(session_id)
        except TmuxError:
            pass  # Session might not exist

        self.create_session(session_id, cwd)

    def list_sessions(self) -> list:
        """List all managed tmux sessions.

        Returns:
            List of session IDs
        """
        return list(self._sessions.keys())

    def get_session_count(self) -> int:
        """Get the number of active sessions.

        Returns:
            Number of active sessions
        """
        return len(self._sessions)
