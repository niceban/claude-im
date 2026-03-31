"""Integration tests for openclaw-claude-bridge.

INTEGRATION TESTS: These tests require the actual claude-node CLI to be installed
and running. They document expected behavior when all components are wired together.

These tests are SKIPPED by default since they require claude-node installation.
Run with: pytest tests/integration/ -v --claude-node-installed
"""

import os
import pytest


# Skip all integration tests unless explicitly enabled
# Run with: pytest tests/integration/ -v -m claude_node_installed
pytestmark = pytest.mark.skip(reason="Requires claude-node CLI installation")


@pytest.fixture
def require_claude_node():
    """Fixture that skips test if claude-node is not installed."""
    import shutil
    if shutil.which("claude") is None:
        pytest.skip("claude-node CLI not installed")
    return True


@pytest.fixture
def integration_config(tmp_path):
    """Provide a Config for integration testing."""
    import sys
    sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")
    from clawrelay_bridge.config import Config

    db_path = tmp_path / "integration_bridge.db"
    return Config(
        host="127.0.0.1",
        port=18793,  # Different port to avoid conflicts
        claude_model="claude-sonnet-4-6",
        claude_working_dir=str(tmp_path),
        health_check_interval=5,
        fallback_failure_threshold=3,
        fallback_success_threshold=3,
        db_path=str(db_path),
    )


class TestClaudeNodeAdapterIntegration:
    """Integration tests for ClaudeNodeAdapter with real claude-node CLI."""

    @pytest.mark.claude_node_installed
    @pytest.mark.asyncio
    async def test_check_health_returns_true_when_claude_running(self, require_claude_node):
        """check_health() should return True when claude-node subprocess is healthy."""
        import sys
        sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")
        from claude_node_adapter import ClaudeNodeAdapter

        adapter = ClaudeNodeAdapter(
            model="claude-sonnet-4-6",
            working_dir="/tmp",
        )
        adapter.prewarm()

        try:
            is_healthy = await adapter.check_health()
            assert is_healthy is True
        finally:
            adapter.stop()

    @pytest.mark.claude_node_installed
    @pytest.mark.asyncio
    async def test_stream_chat_returns_text_delta_events(self, require_claude_node):
        """stream_chat() should yield TextDelta events with assistant responses."""
        import sys
        sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")
        from claude_node_adapter import ClaudeNodeAdapter, TextDelta

        adapter = ClaudeNodeAdapter(
            model="claude-sonnet-4-6",
            working_dir="/tmp",
        )

        messages = [{"role": "user", "content": "Say 'hello' and nothing else."}]
        events = []
        async for event in adapter.stream_chat(messages, session_id="test-integration"):
            events.append(event)
            if isinstance(event, TextDelta):
                break  # Stop after first text response

        adapter.stop()

        text_events = [e for e in events if isinstance(e, TextDelta)]
        assert len(text_events) > 0
        assert "hello" in text_events[0].text.lower()

    @pytest.mark.claude_node_installed
    @pytest.mark.asyncio
    async def test_multiple_sessions_run_in_parallel(self, require_claude_node):
        """Multiple sessions should be able to run in parallel without interference."""
        import sys
        sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")
        from claude_node_adapter import ClaudeNodeAdapter

        adapter = ClaudeNodeAdapter(
            model="claude-sonnet-4-6",
            working_dir="/tmp",
        )

        async def run_session(session_id: str):
            messages = [{"role": "user", "content": f"Say '{session_id}'"}]
            async for event in adapter.stream_chat(messages, session_id=session_id):
                if hasattr(event, 'text'):
                    return event.text
            return ""

        # Run two sessions concurrently
        import asyncio
        results = await asyncio.gather(
            run_session("session-a"),
            run_session("session-b"),
        )

        adapter.stop()

        assert "session-a" in results[0].lower()
        assert "session-b" in results[1].lower()


class TestBridgeServerIntegration:
    """Integration tests for BridgeServer with real HTTP client."""

    @pytest.mark.claude_node_installed
    def test_health_endpoint_with_real_claude(self, require_claude_node, integration_config):
        """GET /health should report claude_node as 'connected' when claude-node is healthy."""
        import sys
        sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")
        from clawrelay_bridge.server import BridgeServer

        server = BridgeServer(integration_config)

        # Wait for health monitor to run at least one check
        import asyncio
        async def wait_for_health():
            for _ in range(10):
                await asyncio.sleep(1)
                if server.health_monitor.get_status().claude_node_connected:
                    return True
            return False

        asyncio.run(server.health_monitor.start())
        asyncio.run(asyncio.sleep(2))  # Give it time to check

        response = asyncio.run(server.health())

        asyncio.run(server.health_monitor.stop())

        assert response.claude_node == "connected"

    @pytest.mark.claude_node_installed
    def test_chat_completions_returns_valid_response(self, require_claude_node, integration_config):
        """POST /v1/chat/completions should return a valid ChatCompletionResponse."""
        import sys
        sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")
        from clawrelay_bridge.server import BridgeServer, ChatCompletionRequest, ChatMessage

        server = BridgeServer(integration_config)

        # Wait for health check
        import asyncio
        asyncio.run(asyncio.sleep(2))

        from fastapi import Request
        mock_request = MagicMock()
        mock_request.headers = {"X-OpenClaw-Session-ID": "test-integration-session"}

        body = ChatCompletionRequest(
            model="claude-sonnet-4-6",
            messages=[ChatMessage(role="user", content="Say 'test'")],
        )

        response = asyncio.run(server.chat_completions(mock_request, body))

        assert response.id.startswith("chatcmpl-")
        assert response.object == "chat.completion"
        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert len(response.choices[0].message.content) > 0


class TestSessionMapperIntegration:
    """Integration tests for SessionMapper with real database."""

    def test_session_persistence_across_restarts(self, tmp_path, require_claude_node):
        """Session mappings should persist and be retrievable after mapper recreation."""
        import sys
        sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")
        from clawrelay_bridge.session_mapper import SessionMapper

        db_path = tmp_path / "persistent_sessions.db"

        # Create mapping with first mapper
        mapper1 = SessionMapper(str(db_path))
        mapper1.create_mapping(
            openclaw_session_id="persistent-001",
            claude_session_id="claude-persistent-001",
            platform="feishu",
            user_id="user-persistent",
        )

        # Recreate mapper (simulating restart)
        mapper2 = SessionMapper(str(db_path))

        # Should still be able to retrieve
        retrieved = mapper2.get_by_openclaw_session("persistent-001")
        assert retrieved is not None
        assert retrieved.openclaw_session_id == "persistent-001"
        assert retrieved.platform == "feishu"
        assert retrieved.user_id == "user-persistent"


class TestFallbackManagerIntegration:
    """Integration tests for FallbackManager behavior with real HealthMonitor."""

    @pytest.mark.asyncio
    async def test_fallback_activates_after_consecutive_failures(self, require_claude_node):
        """Fallback should activate after failure_threshold consecutive unhealthy checks."""
        import sys
        sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")
        from clawrelay_bridge.health_monitor import HealthMonitor
        from clawrelay_bridge.fallback_manager import FallbackManager, FallbackState

        fallback_activated = []

        fallback_manager = FallbackManager(
            failure_threshold=3,
            success_threshold=3,
            on_activate=lambda: fallback_activated.append(True),
        )

        unhealthy_adapter = MagicMock()
        unhealthy_adapter.check_health = AsyncMock(return_value=False)

        health_monitor = HealthMonitor(
            check_interval=1,
            failure_threshold=3,
            on_become_unhealthy=fallback_manager.report_unhealthy,
        )
        health_monitor.set_claude_adapter(unhealthy_adapter)

        # Run failure checks
        for _ in range(3):
            await health_monitor._run_check_cycle()

        # Give callbacks time to process
        await asyncio.sleep(0.1)

        assert fallback_manager.state == FallbackState.FALLBACK
        assert len(fallback_activated) == 1
