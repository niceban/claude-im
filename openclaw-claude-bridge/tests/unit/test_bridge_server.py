"""Unit tests for BridgeServer.

RED PHASE: These tests define expected behavior for the BridgeServer HTTP API.
All tests should FAIL initially until implementation is complete.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

import pytest

from clawrelay_bridge.server import BridgeServer
from clawrelay_bridge.config import Config
from clawrelay_bridge.fallback_manager import FallbackState


class TestBridgeServerHealthEndpoint:
    """Tests for BridgeServer /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_correct_structure(self, temp_db_path, mock_claude_node_adapter):
        """Health endpoint should return HealthResponse with all required fields."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        response = await server.health()

        assert hasattr(response, 'status')
        assert hasattr(response, 'claude_node')
        assert hasattr(response, 'fallback_state')
        assert hasattr(response, 'timestamp')
        assert hasattr(response, 'session_count')

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_unknown_when_no_adapter(self, temp_db_path):
        """Health status should be 'unknown' when no adapter is set."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        # Do not set adapter

        response = await server.health()

        assert response.status == "unknown"
        assert response.claude_node == "disconnected"

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_session_count(self, temp_db_path, mock_claude_node_adapter):
        """Health endpoint should return count of active sessions."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        # Create a session
        server.session_mapper.create_mapping(
            openclaw_session_id="test-session",
            claude_session_id="claude-session",
        )

        response = await server.health()

        assert response.session_count == 1

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_fallback_state(self, temp_db_path, mock_claude_node_adapter):
        """Health endpoint should return current fallback state."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        response = await server.health()

        assert response.fallback_state in ["normal", "fallback"]

    @pytest.mark.asyncio
    async def test_health_endpoint_timestamp_is_iso_format(self, temp_db_path, mock_claude_node_adapter):
        """Health endpoint timestamp should be ISO format string."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        response = await server.health()

        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(response.timestamp)
        assert parsed.year == 2026


class TestBridgeServerSessionIdExtraction:
    """Tests for BridgeServer._get_openclaw_session_id()."""

    def test_extracts_x_openclaw_session_id_header(self, temp_db_path, mock_claude_node_adapter):
        """Should extract session ID from X-OpenClaw-Session-ID header."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)

        mock_request = MagicMock()
        mock_request.headers = {
            "X-OpenClaw-Session-ID": "openclaw-session-123",
            "X-Session-ID": "legacy-session",
        }

        session_id = server._get_openclaw_session_id(mock_request)

        assert session_id == "openclaw-session-123"

    def test_extracts_x_session_id_when_openclaw_header_missing(self, temp_db_path, mock_claude_node_adapter):
        """Should extract session ID from X-Session-ID when X-OpenClaw-Session-ID is missing."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)

        mock_request = MagicMock()
        mock_request.headers = {
            "X-Session-ID": "legacy-session-456",
        }

        session_id = server._get_openclaw_session_id(mock_request)

        assert session_id == "legacy-session-456"

    def test_generates_uuid_when_no_session_header(self, temp_db_path, mock_claude_node_adapter):
        """Should generate a new UUID when no session header is present."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)

        mock_request = MagicMock()
        mock_request.headers = {}

        session_id = server._get_openclaw_session_id(mock_request)

        # Should be a valid UUID format
        assert len(session_id) == 36  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert "-" in session_id

    def test_prefers_openclaw_header_over_legacy(self, temp_db_path, mock_claude_node_adapter):
        """X-OpenClaw-Session-ID should take precedence over X-Session-ID."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)

        mock_request = MagicMock()
        mock_request.headers = {
            "X-OpenClaw-Session-ID": "openclaw-primary",
            "X-Session-ID": "legacy-secondary",
        }

        session_id = server._get_openclaw_session_id(mock_request)

        assert session_id == "openclaw-primary"


class TestBridgeServerFallbackIntegration:
    """Tests for BridgeServer integration with FallbackManager."""

    @pytest.mark.asyncio
    async def test_chat_completions_returns_503_when_fallback_active(self, temp_db_path, mock_claude_node_adapter):
        """POST /v1/chat/completions should return 503 when fallback mode is active."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        # Activate fallback mode
        server.fallback_manager.force_fallback("test")

        mock_request = MagicMock()
        mock_request.headers = {"X-OpenClaw-Session-ID": "test-session"}

        body = MagicMock()
        body.model = "test-model"
        body.messages = [MagicMock()]

        from fastapi import HTTPException

        # Should raise HTTPException with 503
        with pytest.raises(HTTPException) as exc_info:
            await server.chat_completions(mock_request, body)

        assert exc_info.value.status_code == 503
        assert "fallback" in exc_info.value.detail.lower() or "unavailable" in exc_info.value.detail.lower()

    def test_fallback_manager_receives_health_monitor_callbacks(self, temp_db_path, mock_claude_node_adapter):
        """FallbackManager should be connected to HealthMonitor callbacks."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        # Verify callbacks are set
        assert server.health_monitor.on_become_healthy is not None
        assert server.health_monitor.on_become_unhealthy is not None


class TestBridgeServerListModels:
    """Tests for BridgeServer /v1/models endpoint."""

    @pytest.mark.asyncio
    async def test_list_models_returns_model_info(self, temp_db_path, mock_claude_node_adapter):
        """list_models should return ModelListResponse with configured model."""
        config = Config(db_path=temp_db_path)
        config.claude_model = "claude-sonnet-4-6"
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        response = await server.list_models()

        assert len(response.data) == 1
        assert response.data[0].id == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_list_models_response_object_is_list(self, temp_db_path, mock_claude_node_adapter):
        """list_models should return object='list'."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        response = await server.list_models()

        assert response.object == "list"


class TestBridgeServerOnFallbackCallbacks:
    """Tests for BridgeServer fallback activation/deactivation callbacks."""

    def test_on_fallback_activate_logs_warning(self, temp_db_path, mock_claude_node_adapter, caplog):
        """_on_fallback_activate should log a warning message."""
        import logging
        caplog.set_level(logging.WARNING)

        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        server._on_fallback_activate()

        assert any("FALLBACK" in record.message or "fallback" in record.message.lower()
                  for record in caplog.records)

    def test_on_fallback_deactivate_logs_info(self, temp_db_path, mock_claude_node_adapter, caplog):
        """_on_fallback_deactivate should log an info message."""
        import logging
        caplog.set_level(logging.INFO)

        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)
        server.health_monitor.set_claude_adapter(mock_claude_node_adapter)

        server._on_fallback_deactivate()

        assert any("normal" in record.message.lower() or "resuming" in record.message.lower()
                  for record in caplog.records)


class TestBridgeServerConfigInitialization:
    """Tests for BridgeServer initialization with Config."""

    def test_server_accepts_config_object(self, temp_db_path):
        """BridgeServer should accept a Config object as parameter."""
        config = Config(db_path=temp_db_path)

        server = BridgeServer(config)

        assert server.config is not None
        assert server.config.db_path == temp_db_path

    def test_server_creates_session_mapper_from_config(self, temp_db_path):
        """BridgeServer should create SessionMapper with config.db_path."""
        config = Config(db_path=temp_db_path)
        server = BridgeServer(config)

        assert server.session_mapper is not None

    def test_server_creates_health_monitor_from_config(self, temp_db_path):
        """BridgeServer should create HealthMonitor with config settings."""
        config = Config(
            db_path=temp_db_path,
            health_check_interval=60,
            fallback_failure_threshold=5,
            fallback_success_threshold=5,
        )
        server = BridgeServer(config)

        assert server.health_monitor is not None
        assert server.health_monitor.check_interval == 60

    def test_server_creates_fallback_manager_from_config(self, temp_db_path):
        """BridgeServer should create FallbackManager with config settings."""
        config = Config(
            db_path=temp_db_path,
            fallback_failure_threshold=4,
            fallback_success_threshold=2,
        )
        server = BridgeServer(config)

        assert server.fallback_manager is not None
        assert server.fallback_manager.failure_threshold == 4
        assert server.fallback_manager.success_threshold == 2
