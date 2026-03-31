"""Health monitor for claude-node."""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status states."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthState:
    """Current health state."""
    status: HealthStatus = HealthStatus.UNKNOWN
    claude_node_connected: bool = False
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_check: Optional[datetime] = None
    error_message: str = ""


class HealthMonitor:
    """Monitors claude-node health and triggers fallback when needed."""

    def __init__(
        self,
        check_interval: int = 30,
        failure_threshold: int = 3,
        success_threshold: int = 3,
        on_become_healthy: Optional[Callable[[], None]] = None,
        on_become_unhealthy: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize health monitor.

        Args:
            check_interval: Seconds between health checks
            failure_threshold: Consecutive failures before marking unhealthy
            success_threshold: Consecutive successes before marking healthy
            on_become_healthy: Callback when health recovers
            on_become_unhealthy: Callback when health fails (receives error message)
        """
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.on_become_healthy = on_become_healthy
        self.on_become_unhealthy = on_become_unhealthy

        self._state = HealthState()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # ClaudeNodeAdapter reference (set by BridgeServer)
        self._claude_adapter = None

    def set_claude_adapter(self, adapter):
        """Set the claude-node adapter to monitor."""
        self._claude_adapter = adapter

    async def _check_claude_node(self) -> bool:
        """Check if claude-node is healthy."""
        if self._claude_adapter is None:
            return False

        try:
            # Use the adapter's health check
            result = await self._claude_adapter.check_health()
            return result
        except Exception as e:
            logger.warning(f"[HealthMonitor] claude-node health check failed: {e}")
            self._state.error_message = str(e)
            return False

    async def _run_check_cycle(self):
        """Run a single health check cycle."""
        is_healthy = await self._check_claude_node()
        self._state.last_check = datetime.now()

        if is_healthy:
            self._state.claude_node_connected = True
            self._state.consecutive_failures = 0
            self._state.error_message = ""  # Clear error on success
            self._state.consecutive_successes += 1

            if (
                self._state.status == HealthStatus.UNHEALTHY
                and self._state.consecutive_successes >= self.success_threshold
            ):
                logger.info("[HealthMonitor] claude-node recovered!")
                self._state.status = HealthStatus.HEALTHY
                if self.on_become_healthy:
                    self.on_become_healthy()
            elif (
                self._state.status == HealthStatus.UNKNOWN
                and self._state.consecutive_successes >= self.success_threshold
            ):
                # Initial healthy state
                logger.info("[HealthMonitor] claude-node initially healthy")
                self._state.status = HealthStatus.HEALTHY
                if self.on_become_healthy:
                    self.on_become_healthy()

        else:
            self._state.claude_node_connected = False
            self._state.consecutive_successes = 0
            self._state.consecutive_failures += 1

            if (
                self._state.status == HealthStatus.UNHEALTHY
                and self._state.consecutive_failures >= self.failure_threshold
            ):
                logger.warning(f"[HealthMonitor] claude-node unhealthy! (threshold: {self.failure_threshold})")
                # Already unhealthy, just log (callback already fired on transition)
            elif (
                self._state.status == HealthStatus.UNKNOWN
                and self._state.consecutive_failures >= self.failure_threshold
            ):
                # Transition from UNKNOWN to UNHEALTHY
                logger.warning(f"[HealthMonitor] claude-node unhealthy! (threshold: {self.failure_threshold})")
                self._state.status = HealthStatus.UNHEALTHY
                if self.on_become_unhealthy:
                    self.on_become_unhealthy(self._state.error_message or "claude-node not responding")
            elif (
                self._state.status == HealthStatus.HEALTHY
                and self._state.consecutive_failures >= self.failure_threshold
            ):
                # Transition from HEALTHY to UNHEALTHY
                logger.warning(f"[HealthMonitor] claude-node unhealthy! (threshold: {self.failure_threshold})")
                self._state.status = HealthStatus.UNHEALTHY
                if self.on_become_unhealthy:
                    self.on_become_unhealthy(self._state.error_message or "claude-node not responding")

        logger.debug(
            f"[HealthMonitor] Check #{self._state.consecutive_successes + self._state.consecutive_failures}: "
            f"healthy={is_healthy}, failures={self._state.consecutive_failures}, "
            f"successes={self._state.consecutive_successes}"
        )

    async def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info(f"[HealthMonitor] Started with interval={self.check_interval}s")

        while self._running:
            try:
                await self._run_check_cycle()
            except Exception as e:
                logger.error(f"[HealthMonitor] Check cycle failed: {e}")

            await asyncio.sleep(self.check_interval)

        logger.info("[HealthMonitor] Stopped")

    def start(self):
        """Start the health monitor."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("[HealthMonitor] Starting health monitor")

    async def stop(self):
        """Stop the health monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def get_status(self) -> HealthState:
        """Get current health status."""
        return self._state

    def is_healthy(self) -> bool:
        """Check if system is currently healthy."""
        return self._state.status == HealthStatus.HEALTHY
