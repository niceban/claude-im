"""Pytest fixtures and shared test utilities."""

import os
import tempfile
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Use src path for imports
import sys
sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0] + "/src")


@pytest.fixture
def temp_db_path(tmp_path) -> str:
    """Provide a temporary database path for SessionMapper tests."""
    db_file = tmp_path / "test_bridge.db"
    return str(db_file)


@pytest.fixture
def mock_claude_node_adapter():
    """
    Mock ClaudeNodeAdapter for unit tests.

    Returns a mock that simulates claude-node behavior without requiring
    the actual claude-node CLI to be installed.
    """
    adapter = MagicMock()
    adapter.check_health = AsyncMock(return_value=True)
    # Use a proper async generator mock
    async def mock_stream_chat(*args, **kwargs):
        return  # Empty async generator
        yield  # Make it an async generator
    adapter.stream_chat = MagicMock(side_effect=mock_stream_chat)
    adapter.prewarm = MagicMock()
    adapter.stop = MagicMock()
    adapter.alive = True
    return adapter


@pytest.fixture
def mock_unhealthy_claude_node_adapter():
    """Mock an unhealthy ClaudeNodeAdapter for failure scenario tests."""
    adapter = MagicMock()
    adapter.check_health = AsyncMock(return_value=False)
    async def mock_stream_chat(*args, **kwargs):
        return  # Empty async generator
        yield  # Make it an async generator
    adapter.stream_chat = MagicMock(side_effect=mock_stream_chat)
    adapter.prewarm = MagicMock()
    adapter.stop = MagicMock()
    adapter.alive = False
    return adapter


@pytest.fixture
def sample_config():
    """Provide a test Config instance."""
    from clawrelay_bridge.config import Config
    config = Config(
        host="127.0.0.1",
        port=18792,
        claude_model="claude-sonnet-4-6",
        claude_working_dir="/tmp/test",
        health_check_interval=5,
        fallback_failure_threshold=3,
        fallback_success_threshold=3,
        db_path="",  # Will be overridden by temp_db_path fixture
    )
    return config


@pytest.fixture
def sample_session_mapping_data():
    """Provide sample session mapping data for testing."""
    return {
        "id": 1,
        "openclaw_session_id": "test-openclaw-session-123",
        "claude_session_id": "test-claude-session-456",
        "platform": "feishu",
        "user_id": "user-789",
        "created_at": "2026-03-29T12:00:00",
        "last_active": 1743340800.0,
        "status": "active",
    }


@pytest.fixture
def mock_request_headers():
    """Provide mock FastAPI request headers."""
    return {
        "X-OpenClaw-Session-ID": "test-session-from-header",
        "X-Session-ID": "legacy-session-id",
    }
