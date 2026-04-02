"""Tests for openai-compatible-api module."""
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.applications import Starlette
from starlette.routing import Route
from unittest.mock import patch
import importlib
import os

# Set API key before importing server - must be done before import
os.environ["BRIDGE_API_KEY"] = "test-key"

# Force reload to pick up env
import openai_compatible_api.server as server_module
importlib.reload(server_module)

from openai_compatible_api.server import (
    app, chat_completions, health, list_models, validate_api_key
)
from openai_compatible_api.errors import (
    ERROR_MISSING_API_KEY, ERROR_INVALID_API_KEY, ERROR_MISSING_FIELD,
    ERROR_MODEL_NOT_FOUND
)


@pytest.fixture
def test_app():
    """Create test app with routes."""
    routes = [
        Route("/v1/chat/completions", chat_completions, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
        Route("/v1/models", list_models, methods=["GET"]),
    ]
    return Starlette(routes=routes)


@pytest.mark.asyncio
async def test_chat_completions_missing_api_key(test_app):
    """Test missing API key returns 401."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "hello"}]}
        )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["type"] == "authentication_error"
    assert data["error"]["code"] == "missing_api_key"
    assert data["error"]["status"] == 401


@pytest.mark.asyncio
async def test_chat_completions_invalid_api_key(test_app):
    """Test invalid API key returns 401."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "hello"}]},
            headers={"X-API-Key": "wrong-key"}
        )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["message"] == "Invalid API Key"


@pytest.mark.asyncio
async def test_chat_completions_missing_messages():
    """Test missing messages field returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "claude-sonnet-4-6"},
            headers={"X-API-Key": "test-key"}
        )
    assert response.status_code == 400
    data = response.json()
    assert "Missing required field" in data["error"]["message"]


@pytest.mark.asyncio
async def test_chat_completions_model_not_found():
    """Test unknown model returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "unknown-model", "messages": [{"role": "user", "content": "hello"}]},
            headers={"X-API-Key": "test-key"}
        )
    assert response.status_code == 400
    data = response.json()
    assert "Model not found" in data["error"]["message"]


@pytest.mark.asyncio
async def test_chat_completions_success():
    """Test successful chat completion returns expected structure."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "hello"}]},
            headers={"X-API-Key": "test-key"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["object"] == "chat.completion"
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert "usage" in data
    assert "prompt_tokens" in data["usage"]
    assert "completion_tokens" in data["usage"]
    assert "total_tokens" in data["usage"]


@pytest.mark.asyncio
async def test_chat_completions_not_placeholder():
    """Test chat completion returns REAL response, not placeholder (Task 1.1.2)."""
    from unittest.mock import patch, MagicMock

    # Mock adapter.send_message to return a real response
    mock_result = {
        "text": "Hello! How can I help you today?",
        "prompt_tokens": 10,
        "completion_tokens": 15,
        "total_tokens": 25
    }

    with patch('openai_compatible_api.server.get_process_manager') as mock_get_pm:
        mock_pm = MagicMock()
        mock_pm.send_message.return_value = mock_result
        mock_get_pm.return_value = mock_pm

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "hello"}]},
                headers={"X-API-Key": "test-key"}
            )

    assert response.status_code == 200
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    # MUST NOT be placeholder
    assert content != "(placeholder - adapter not yet connected)", f"Got placeholder: {content}"
    assert "Hello" in content  # Real response should contain actual text


@pytest.mark.asyncio
async def test_chat_completions_with_adapter_error():
    """Test adapter errors are properly formatted as API errors (Task 1.1.3)."""
    from unittest.mock import patch, MagicMock

    # Mock adapter to return an error
    mock_result = {
        "error": {
            "type": "timeout",
            "message": "Request timeout after 120s"
        }
    }

    with patch('openai_compatible_api.server.get_process_manager') as mock_get_pm:
        mock_pm = MagicMock()
        mock_pm.send_message.return_value = mock_result
        mock_get_pm.return_value = mock_pm

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "hello"}]},
                headers={"X-API-Key": "test-key"}
            )

    # Should return error response
    assert response.status_code == 504  # Timeout
    data = response.json()
    assert "error" in data
    assert "message" in data["error"]


@pytest.mark.asyncio
async def test_chat_completions_session_id_extraction():
    """Test conversation_id is extracted and passed to adapter (Task 1.1.4)."""
    from unittest.mock import patch, MagicMock

    mock_result = {
        "text": "Real response",
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8
    }

    with patch('openai_compatible_api.server.get_process_manager') as mock_get_pm:
        mock_pm = MagicMock()
        mock_pm.send_message.return_value = mock_result
        mock_get_pm.return_value = mock_pm

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "claude-sonnet-4-6",
                    "messages": [{"role": "user", "content": "hello"}],
                    "conversation_id": "test-conv-123"
                },
                headers={"X-API-Key": "test-key"}
            )

        # Verify adapter was called with session_id
        mock_pm.send_message.assert_called_once()
        call_args = mock_pm.send_message.call_args
        # session_id should be extracted from conversation_id
        assert "test-conv-123" in str(call_args)


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health endpoint returns version dynamically."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_list_models():
    """Test list models endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/models", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert "data" in data
    assert len(data["data"]) > 0
    assert data["data"][0]["id"] == "claude-sonnet-4-6"
