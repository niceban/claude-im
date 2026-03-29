"""Fallback manager for OpenClaw activation when claude-node fails."""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class FallbackState(Enum):
    """Fallback state machine states."""
    NORMAL = "normal"      # claude-node is healthy, OpenClaw is silent
    FALLBACK = "fallback"  # claude-node is unhealthy, OpenClaw is active


@dataclass
class FallbackTransition:
    """Represents a state transition."""
    from_state: FallbackState
    to_state: FallbackState
    reason: str


class FallbackManager:
    """
    Manages fallback activation when claude-node goes down.

    State machine:
    - NORMAL: claude-node is healthy, OpenClaw is silent
    - FALLBACK: claude-node is unhealthy, OpenClaw is active for repairs
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        success_threshold: int = 3,
        on_activate: Optional[Callable[[], None]] = None,
        on_deactivate: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize fallback manager.

        Args:
            failure_threshold: Consecutive failures before activating fallback
            success_threshold: Consecutive successes before deactivating fallback
            on_activate: Callback when fallback is activated
            on_deactivate: Callback when fallback is deactivated
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.on_activate = on_activate
        self.on_deactivate = on_deactivate

        self._state = FallbackState.NORMAL
        self._failure_count = 0
        self._success_count = 0

    @property
    def state(self) -> FallbackState:
        """Get current fallback state."""
        return self._state

    @property
    def is_fallback_active(self) -> bool:
        """Check if fallback mode is currently active."""
        return self._state == FallbackState.FALLBACK

    def report_healthy(self):
        """
        Report that claude-node is healthy.
        Called by HealthMonitor when health check succeeds.
        """
        if self._state == FallbackState.FALLBACK:
            self._success_count += 1
            self._failure_count = 0

            if self._success_count >= self.success_threshold:
                self._transition_to(FallbackState.NORMAL, "claude-node recovered")

        elif self._state == FallbackState.NORMAL:
            # Reset counters when in normal state
            self._failure_count = 0
            self._success_count = 0

    def report_unhealthy(self, reason: str = ""):
        """
        Report that claude-node is unhealthy.
        Called by HealthMonitor when health check fails.
        """
        if self._state == FallbackState.NORMAL:
            self._failure_count += 1
            self._success_count = 0

            if self._failure_count >= self.failure_threshold:
                self._transition_to(FallbackState.FALLBACK, reason or "claude-node failure threshold reached")

        elif self._state == FallbackState.FALLBACK:
            # Reset success count when in fallback state
            self._success_count = 0

    def _transition_to(self, new_state: FallbackState, reason: str):
        """Transition to a new state."""
        if self._state == new_state:
            return

        old_state = self._state
        self._state = new_state

        logger.info(f"[FallbackManager] State transition: {old_state.value} -> {new_state.value} ({reason})")

        if new_state == FallbackState.FALLBACK:
            if self.on_activate:
                try:
                    self.on_activate()
                except Exception as e:
                    logger.error(f"[FallbackManager] on_activate callback failed: {e}")
        elif new_state == FallbackState.NORMAL:
            if self.on_deactivate:
                try:
                    self.on_deactivate()
                except Exception as e:
                    logger.error(f"[FallbackManager] on_deactivate callback failed: {e}")

    def force_fallback(self, reason: str = "manual"):
        """Force activate fallback mode."""
        if self._state != FallbackState.FALLBACK:
            self._transition_to(FallbackState.FALLBACK, f"forced: {reason}")

    def force_normal(self, reason: str = "manual"):
        """Force deactivate fallback mode."""
        if self._state == FallbackState.FALLBACK:
            self._transition_to(FallbackState.NORMAL, f"forced: {reason}")
