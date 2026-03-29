"""Unit tests for HealthMonitor.

RED PHASE: These tests define expected behavior for health monitoring.
All tests should FAIL initially until implementation is complete.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clawrelay_bridge.health_monitor import HealthMonitor, HealthState, HealthStatus


class TestHealthMonitorInitialState:
    """Tests for HealthMonitor initial state."""

    def test_initial_status_is_unknown(self):
        """HealthMonitor should start with UNKNOWN status."""
        monitor = HealthMonitor()

        state = monitor.get_status()
        assert state.status == HealthStatus.UNKNOWN

    def test_initial_claude_node_connected_is_false(self):
        """HealthMonitor should start with claude_node_connected=False."""
        monitor = HealthMonitor()

        state = monitor.get_status()
        assert state.claude_node_connected is False

    def test_initial_consecutive_failures_is_zero(self):
        """HealthMonitor should have consecutive_failures=0 initially."""
        monitor = HealthMonitor()

        state = monitor.get_status()
        assert state.consecutive_failures == 0

    def test_initial_consecutive_successes_is_zero(self):
        """HealthMonitor should have consecutive_successes=0 initially."""
        monitor = HealthMonitor()

        state = monitor.get_status()
        assert state.consecutive_successes == 0

    def test_initial_error_message_is_empty(self):
        """HealthMonitor should have empty error_message initially."""
        monitor = HealthMonitor()

        state = monitor.get_status()
        assert state.error_message == ""

    def test_is_healthy_returns_false_initially(self):
        """is_healthy() should return False initially."""
        monitor = HealthMonitor()

        assert monitor.is_healthy() is False


class TestHealthMonitorWithMockedAdapter:
    """Tests for HealthMonitor with mocked claude-node adapter."""

    @pytest.mark.asyncio
    async def test_reports_unhealthy_when_adapter_is_none(self):
        """HealthMonitor should report unhealthy when adapter is None."""
        monitor = HealthMonitor()
        # Do not set adapter - leave it as None

        is_healthy = await monitor._check_claude_node()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_reports_healthy_when_adapter_check_returns_true(self, mock_claude_node_adapter):
        """HealthMonitor should report healthy when adapter.check_health() returns True."""
        monitor = HealthMonitor()
        monitor.set_claude_adapter(mock_claude_node_adapter)

        is_healthy = await monitor._check_claude_node()

        assert is_healthy is True
        mock_claude_node_adapter.check_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_reports_unhealthy_when_adapter_check_returns_false(self, mock_unhealthy_claude_node_adapter):
        """HealthMonitor should report unhealthy when adapter.check_health() returns False."""
        monitor = HealthMonitor()
        monitor.set_claude_adapter(mock_unhealthy_claude_node_adapter)

        is_healthy = await monitor._check_claude_node()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_reports_unhealthy_when_adapter_check_raises_exception(self):
        """HealthMonitor should report unhealthy when adapter.check_health() raises."""
        monitor = HealthMonitor()
        bad_adapter = MagicMock()
        bad_adapter.check_health = AsyncMock(side_effect=RuntimeError("Connection refused"))
        monitor.set_claude_adapter(bad_adapter)

        is_healthy = await monitor._check_claude_node()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_check_cycle_increments_failures_on_unhealthy(self, mock_unhealthy_claude_node_adapter):
        """_run_check_cycle should increment consecutive_failures on unhealthy check."""
        monitor = HealthMonitor()
        monitor.set_claude_adapter(mock_unhealthy_claude_node_adapter)

        await monitor._run_check_cycle()

        state = monitor.get_status()
        assert state.consecutive_failures == 1
        assert state.consecutive_successes == 0

    @pytest.mark.asyncio
    async def test_check_cycle_increments_successes_on_healthy(self, mock_claude_node_adapter):
        """_run_check_cycle should increment consecutive_successes on healthy check."""
        monitor = HealthMonitor()
        monitor.set_claude_adapter(mock_claude_node_adapter)

        await monitor._run_check_cycle()

        state = monitor.get_status()
        assert state.consecutive_successes == 1
        assert state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_multiple_failures_increment_counter(self, mock_unhealthy_claude_node_adapter):
        """Multiple consecutive unhealthy checks should increment failure counter."""
        monitor = HealthMonitor(failure_threshold=3)
        monitor.set_claude_adapter(mock_unhealthy_claude_node_adapter)

        await monitor._run_check_cycle()
        await monitor._run_check_cycle()
        await monitor._run_check_cycle()

        state = monitor.get_status()
        assert state.consecutive_failures == 3
        assert state.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_failure_threshold_triggers_unhealthy_callback(self, mock_unhealthy_claude_node_adapter):
        """When failure_threshold is reached, on_become_unhealthy callback should be called."""
        callback_received = []

        def on_become_unhealthy(msg):
            callback_received.append(msg)

        monitor = HealthMonitor(failure_threshold=2, on_become_unhealthy=on_become_unhealthy)
        monitor.set_claude_adapter(mock_unhealthy_claude_node_adapter)

        await monitor._run_check_cycle()
        await monitor._run_check_cycle()

        assert len(callback_received) == 1
        assert "claude-node not responding" in callback_received[0] or callback_received[0] != ""

    @pytest.mark.asyncio
    async def test_recovery_requires_success_threshold(self, mock_claude_node_adapter):
        """Recovery from UNHEALTHY should require consecutive_successes >= success_threshold."""
        monitor = HealthMonitor(failure_threshold=1, success_threshold=3)
        monitor.set_claude_adapter(mock_claude_node_adapter)

        # First make it unhealthy
        mock_adapter_unhealthy = MagicMock()
        mock_adapter_unhealthy.check_health = AsyncMock(return_value=False)
        monitor.set_claude_adapter(mock_adapter_unhealthy)
        await monitor._run_check_cycle()
        assert monitor.get_status().status == HealthStatus.UNHEALTHY

        # Now report healthy
        monitor.set_claude_adapter(mock_claude_node_adapter)
        await monitor._run_check_cycle()
        await monitor._run_check_cycle()
        # Still unhealthy - need 3 successes
        assert monitor.get_status().status == HealthStatus.UNHEALTHY

        await monitor._run_check_cycle()
        # Now should be healthy
        assert monitor.get_status().status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_on_become_healthy_callback_invoked_on_recovery(self, mock_claude_node_adapter):
        """on_become_healthy callback should be called when recovering from unhealthy."""
        callback_called = []

        def on_become_healthy():
            callback_called.append(True)

        monitor = HealthMonitor(
            failure_threshold=1,
            success_threshold=1,
            on_become_healthy=on_become_healthy,
        )

        # Make unhealthy first
        unhealthy_adapter = MagicMock()
        unhealthy_adapter.check_health = AsyncMock(return_value=False)
        monitor.set_claude_adapter(unhealthy_adapter)
        await monitor._run_check_cycle()

        # Recover
        monitor.set_claude_adapter(mock_claude_node_adapter)
        await monitor._run_check_cycle()

        assert len(callback_called) == 1


class TestHealthMonitorLifecycle:
    """Tests for HealthMonitor start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running_to_true(self):
        """start() should set _running to True."""
        monitor = HealthMonitor()

        monitor.start()

        assert monitor._running is True

        # Cleanup
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_start_creates_monitoring_task(self):
        """start() should create an asyncio task for the monitoring loop."""
        monitor = HealthMonitor()

        monitor.start()

        assert monitor._task is not None
        assert isinstance(monitor._task, asyncio.Task)

        # Cleanup
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_running_to_false(self):
        """stop() should set _running to False."""
        monitor = HealthMonitor()
        monitor.start()

        await monitor.stop()

        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_monitoring_task(self):
        """stop() should cancel the monitoring task."""
        monitor = HealthMonitor()
        monitor.start()

        await monitor.stop()

        assert monitor._task is None

    @pytest.mark.asyncio
    async def test_double_start_does_nothing(self):
        """Calling start() when already running should do nothing."""
        monitor = HealthMonitor()

        monitor.start()
        task1 = monitor._task
        monitor.start()  # Should not create new task

        assert monitor._task is task1

        # Cleanup
        await monitor.stop()


class TestHealthMonitorLastCheck:
    """Tests for HealthMonitor last_check timestamp tracking."""

    @pytest.mark.asyncio
    async def test_last_check_is_updated_after_check_cycle(self, mock_claude_node_adapter):
        """last_check should be updated after each _run_check_cycle."""
        monitor = HealthMonitor()
        monitor.set_claude_adapter(mock_claude_node_adapter)

        await monitor._run_check_cycle()

        state = monitor.get_status()
        assert state.last_check is not None

    @pytest.mark.asyncio
    async def test_last_check_contains_datetime_object(self, mock_claude_node_adapter):
        """last_check should be a datetime object."""
        monitor = HealthMonitor()
        monitor.set_claude_adapter(mock_claude_node_adapter)

        await monitor._run_check_cycle()

        state = monitor.get_status()
        assert hasattr(state.last_check, 'year')
        assert hasattr(state.last_check, 'month')
        assert hasattr(state.last_check, 'day')


class TestHealthMonitorErrorMessage:
    """Tests for HealthMonitor error message propagation."""

    @pytest.mark.asyncio
    async def test_error_message_captured_from_exception(self):
        """Error message from failed health check should be captured in state."""
        monitor = HealthMonitor()
        bad_adapter = MagicMock()
        bad_adapter.check_health = AsyncMock(side_effect=RuntimeError("Connection refused"))
        monitor.set_claude_adapter(bad_adapter)

        await monitor._run_check_cycle()

        state = monitor.get_status()
        assert "Connection refused" in state.error_message

    @pytest.mark.asyncio
    async def test_error_message_cleared_on_success(self, mock_claude_node_adapter):
        """error_message should be cleared when health check succeeds."""
        monitor = HealthMonitor()
        # First fail
        bad_adapter = MagicMock()
        bad_adapter.check_health = AsyncMock(side_effect=RuntimeError("Connection refused"))
        monitor.set_claude_adapter(bad_adapter)
        await monitor._run_check_cycle()

        # Now succeed
        monitor.set_claude_adapter(mock_claude_node_adapter)
        await monitor._run_check_cycle()

        state = monitor.get_status()
        assert state.error_message == ""


