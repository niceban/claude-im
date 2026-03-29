"""Unit tests for FallbackManager.

RED PHASE: These tests define expected behavior for fallback state management.
All tests should FAIL initially until implementation is complete.
"""

import pytest

from clawrelay_bridge.fallback_manager import FallbackManager, FallbackState


class TestFallbackManagerInitialState:
    """Tests for FallbackManager initial state."""

    def test_initial_state_is_normal(self):
        """FallbackManager should start in NORMAL state."""
        manager = FallbackManager()

        assert manager.state == FallbackState.NORMAL
        assert manager.is_fallback_active is False

    def test_initial_state_with_default_thresholds(self):
        """FallbackManager should have default thresholds of 3 for both failure and success."""
        manager = FallbackManager()

        assert manager.failure_threshold == 3
        assert manager.success_threshold == 3

    def test_initial_failure_count_is_zero(self):
        """FallbackManager should have _failure_count of 0 initially."""
        manager = FallbackManager()

        # These are internal state, but we verify through behavior
        assert manager.state == FallbackState.NORMAL


class TestFallbackManagerStateTransitions:
    """Tests for FallbackManager state transitions."""

    def test_three_consecutive_failures_activates_fallback(self):
        """3 consecutive failures should transition from NORMAL to FALLBACK."""
        manager = FallbackManager(failure_threshold=3, success_threshold=3)

        manager.report_unhealthy("first failure")
        assert manager.state == FallbackState.NORMAL

        manager.report_unhealthy("second failure")
        assert manager.state == FallbackState.NORMAL

        manager.report_unhealthy("third failure")
        assert manager.state == FallbackState.FALLBACK
        assert manager.is_fallback_active is True

    def test_three_consecutive_failures_with_custom_threshold(self):
        """Custom failure_threshold should work correctly."""
        manager = FallbackManager(failure_threshold=5, success_threshold=3)

        for i in range(4):
            manager.report_unhealthy(f"failure {i+1}")
        assert manager.state == FallbackState.NORMAL

        manager.report_unhealthy("fifth failure")
        assert manager.state == FallbackState.FALLBACK

    def test_three_consecutive_successes_in_fallback_deactivates(self):
        """3 consecutive successes while in FALLBACK should transition to NORMAL."""
        manager = FallbackManager(failure_threshold=3, success_threshold=3)

        # First trigger fallback
        manager.report_unhealthy("failure 1")
        manager.report_unhealthy("failure 2")
        manager.report_unhealthy("failure 3")
        assert manager.state == FallbackState.FALLBACK

        # Now report successes
        manager.report_healthy()
        assert manager.state == FallbackState.FALLBACK

        manager.report_healthy()
        assert manager.state == FallbackState.FALLBACK

        manager.report_healthy()
        assert manager.state == FallbackState.NORMAL
        assert manager.is_fallback_active is False

    def test_success_count_resets_on_failure_in_fallback(self):
        """Success count should reset when failure is reported while in FALLBACK."""
        manager = FallbackManager(failure_threshold=3, success_threshold=3)

        # Trigger fallback
        manager.report_unhealthy("failure 1")
        manager.report_unhealthy("failure 2")
        manager.report_unhealthy("failure 3")
        assert manager.state == FallbackState.FALLBACK

        # Report 2 successes
        manager.report_healthy()
        manager.report_healthy()
        assert manager.state == FallbackState.FALLBACK

        # Report failure - should reset success count
        manager.report_unhealthy("failure while in fallback")
        assert manager._success_count == 0

        # Need 3 more successes to recover
        manager.report_healthy()
        manager.report_healthy()
        manager.report_healthy()
        assert manager.state == FallbackState.NORMAL

    def test_failure_count_resets_on_success_in_normal(self):
        """Failure count should reset when success is reported while in NORMAL."""
        manager = FallbackManager(failure_threshold=3, success_threshold=3)

        # Report 2 failures
        manager.report_unhealthy("failure 1")
        manager.report_unhealthy("failure 2")
        assert manager.state == FallbackState.NORMAL

        # Report success - resets failure count
        manager.report_healthy()

        # Need 3 failures again to trigger fallback
        manager.report_unhealthy("failure 1")
        manager.report_unhealthy("failure 2")
        assert manager.state == FallbackState.NORMAL

        manager.report_unhealthy("failure 3")
        assert manager.state == FallbackState.FALLBACK


class TestFallbackManagerCallbacks:
    """Tests for FallbackManager callback invocation."""

    def test_on_activate_callback_is_called_on_fallback_activation(self):
        """on_activate callback should be called when fallback is activated."""
        callback_called = []

        def on_activate():
            callback_called.append(True)

        manager = FallbackManager(
            failure_threshold=3,
            success_threshold=3,
            on_activate=on_activate,
        )

        # Trigger fallback
        manager.report_unhealthy("failure 1")
        manager.report_unhealthy("failure 2")
        manager.report_unhealthy("failure 3")

        assert len(callback_called) == 1
        assert manager.state == FallbackState.FALLBACK

    def test_on_deactivate_callback_is_called_on_recovery(self):
        """on_deactivate callback should be called when returning to NORMAL."""
        callback_called = []

        def on_deactivate():
            callback_called.append(True)

        manager = FallbackManager(
            failure_threshold=3,
            success_threshold=3,
            on_activate=None,
            on_deactivate=on_deactivate,
        )

        # Trigger fallback
        manager.report_unhealthy("failure 1")
        manager.report_unhealthy("failure 2")
        manager.report_unhealthy("failure 3")
        assert manager.state == FallbackState.FALLBACK

        # Recover
        manager.report_healthy()
        manager.report_healthy()
        manager.report_healthy()

        assert len(callback_called) == 1
        assert manager.state == FallbackState.NORMAL

    def test_on_activate_callback_receives_no_arguments(self):
        """on_activate callback should be called with no arguments."""
        received_args = []

        def on_activate(*args):
            received_args.append(args)

        manager = FallbackManager(
            failure_threshold=1,
            on_activate=on_activate,
        )

        manager.report_unhealthy("failure")

        assert len(received_args) == 1
        assert received_args[0] == ()

    def test_on_deactivate_callback_receives_no_arguments(self):
        """on_deactivate callback should be called with no arguments."""
        received_args = []

        def on_deactivate(*args):
            received_args.append(args)

        manager = FallbackManager(
            failure_threshold=1,
            success_threshold=1,
            on_deactivate=on_deactivate,
        )

        # Trigger and recover
        manager.report_unhealthy("failure")
        manager.report_healthy()

        assert len(received_args) == 1
        assert received_args[0] == ()

    def test_callback_exception_does_not_crash_manager(self):
        """Exception in callback should not affect manager state."""
        def bad_callback():
            raise RuntimeError("Callback error")

        manager = FallbackManager(
            failure_threshold=3,
            success_threshold=3,
            on_activate=bad_callback,
        )

        # Should not raise, just log error
        manager.report_unhealthy("failure 1")
        manager.report_unhealthy("failure 2")
        manager.report_unhealthy("failure 3")

        assert manager.state == FallbackState.FALLBACK


class TestFallbackManagerForceMethods:
    """Tests for FallbackManager force_* methods."""

    def test_force_fallback_transitions_to_fallback(self):
        """force_fallback should immediately transition to FALLBACK state."""
        manager = FallbackManager()

        manager.force_fallback("testing")

        assert manager.state == FallbackState.FALLBACK
        assert manager.is_fallback_active is True

    def test_force_fallback_does_nothing_if_already_in_fallback(self):
        """force_fallback should be idempotent."""
        manager = FallbackManager()

        manager.force_fallback("first")
        manager.force_fallback("second")

        assert manager.state == FallbackState.FALLBACK

    def test_force_normal_transitions_to_normal(self):
        """force_normal should immediately transition to NORMAL state."""
        manager = FallbackManager()

        manager.force_fallback()
        manager.force_normal("testing")

        assert manager.state == FallbackState.NORMAL
        assert manager.is_fallback_active is False

    def test_force_normal_does_nothing_if_already_in_normal(self):
        """force_normal should be idempotent."""
        manager = FallbackManager()

        manager.force_normal("testing")

        assert manager.state == FallbackState.NORMAL


class TestFallbackManagerEdgeCases:
    """Edge case tests for FallbackManager."""

    def test_failure_threshold_of_one(self):
        """failure_threshold=1 should trigger fallback on first failure."""
        manager = FallbackManager(failure_threshold=1, success_threshold=1)

        manager.report_unhealthy("first")

        assert manager.state == FallbackState.FALLBACK

    def test_success_threshold_of_one(self):
        """success_threshold=1 should recover on first success."""
        manager = FallbackManager(failure_threshold=1, success_threshold=1)

        manager.report_unhealthy("failure")
        assert manager.state == FallbackState.FALLBACK

        manager.report_healthy()
        assert manager.state == FallbackState.NORMAL

    def test_zero_threshold_triggers_immediately(self):
        """threshold=0 means immediate trigger on first event."""
        manager = FallbackManager(failure_threshold=0, success_threshold=0)

        # First failure triggers fallback immediately (0 >= 0)
        manager.report_unhealthy("failure 1")
        assert manager.state == FallbackState.FALLBACK

        # Reset and first success in fallback also recovers immediately
        manager = FallbackManager(failure_threshold=0, success_threshold=0)
        manager.force_fallback()  # Manually enter fallback
        manager.report_healthy()
        assert manager.state == FallbackState.NORMAL
