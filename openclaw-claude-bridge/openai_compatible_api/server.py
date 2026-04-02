"""OpenAI-compatible API server using Starlette."""
import asyncio
import time
import uuid
from typing import Optional, List, Dict, Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from openai_compatible_api.errors import (
    ERROR_MISSING_API_KEY,
    ERROR_INVALID_API_KEY,
    ERROR_MISSING_FIELD,
    ERROR_MODEL_NOT_FOUND,
    ERROR_RATE_LIMIT,
    ERROR_INTERNAL,
    ERROR_TIMEOUT,
)
from config.settings import API_KEY
from claude_node_adapter.adapter import get_process_manager


# Known models
KNOWN_MODELS = [
    {"id": "claude-sonnet-4-6", "name": "claude-sonnet-4-6", "context_window": 200000},
    {"id": "claude-opus-4-6", "name": "claude-opus-4-6", "context_window": 200000},
    {"id": "claude-haiku-4-5", "name": "claude-haiku-4-5", "context_window": 200000},
]


def get_version() -> str:
    """Get version from package metadata."""
    try:
        from importlib.metadata import version
        return version("openclaw-claude-bridge")
    except Exception:
        return "0.1.0"


async def validate_api_key(request: Request) -> Optional[JSONResponse]:
    """Validate API key from request headers. Returns error response if invalid."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(
            status_code=401,
            content=ERROR_MISSING_API_KEY.to_dict()
        )
    if api_key != API_KEY:
        return JSONResponse(
            status_code=401,
            content=ERROR_INVALID_API_KEY.to_dict()
        )
    return None


async def chat_completions(request: Request):
    """Handle POST /v1/chat/completions.

    Supports both streaming (stream=true) and non-streaming (stream=false) modes.
    """
    # Validate API key
    auth_error = await validate_api_key(request)
    if auth_error:
        return auth_error

    # Parse body
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=ERROR_MISSING_FIELD("messages").to_dict()
        )

    # Validate required fields
    model = body.get("model")
    messages = body.get("messages")
    stream = body.get("stream", False)
    conversation_id = body.get("conversation_id", str(uuid.uuid4()))

    if not model:
        return JSONResponse(
            status_code=400,
            content=ERROR_MISSING_FIELD("model").to_dict()
        )
    if not messages:
        return JSONResponse(
            status_code=400,
            content=ERROR_MISSING_FIELD("messages").to_dict()
        )

    # Validate model
    if not any(m["id"] == model for m in KNOWN_MODELS):
        return JSONResponse(
            status_code=400,
            content=ERROR_MODEL_NOT_FOUND(model).to_dict()
        )

    prompt = _format_messages(messages)
    adapter = get_process_manager()

    # Streaming mode (task 5.2.1)
    if stream:
        stream_id = conversation_id

        async def event_generator():
            # Start async streaming (non-blocking send)
            adapter.send_message_stream(prompt, conversation_id, stream_id)

            # Yield SSE chunks from the stream
            async for chunk in adapter.stream_generator(stream_id, timeout=120):
                yield chunk

            # Send final [DONE] marker
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )

    # Non-streaming mode (task 5.2.4)
    try:
        result = adapter.send_message(
            prompt=prompt,
            session_id=conversation_id
        )

        # Check for error in result
        if "error" in result:
            error = result["error"]
            error_type = error.get("type", "internal_error")
            status_code = 500
            if error_type == "timeout":
                status_code = 504
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": {
                        "message": error.get("message", "Request failed"),
                        "type": error_type,
                        "code": error.get("code", status_code),
                        "param": None,
                        "status": status_code
                    }
                }
            )

        # Format successful response (OpenAI standard)
        return JSONResponse(
            status_code=200,
            content={
                "id": f"chatcmpl-{conversation_id[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result.get("text", result.get("content", ""))
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": result.get("prompt_tokens", 0),
                    "completion_tokens": result.get("completion_tokens", 0),
                    "total_tokens": result.get("total_tokens", 0)
                }
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": 500,
                    "param": None,
                    "status": 500
                }
            }
        )


def _format_messages(messages: list) -> str:
    """Format messages list into a prompt string."""
    formatted = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        formatted.append(f"{role}: {content}")
    return "\n".join(formatted)


async def health(request: Request) -> JSONResponse:
    """Handle GET /health."""
    return JSONResponse({
        "status": "healthy",
        "timestamp": int(time.time()),
        "version": get_version()
    })


async def list_models(request: Request) -> JSONResponse:
    """Handle GET /v1/models."""
    # Validate API key
    auth_error = await validate_api_key(request)
    if auth_error:
        return auth_error

    return JSONResponse({
        "object": "list",
        "data": [
            {
                "id": m["id"],
                "object": "model",
                "created": 1700000000,
                "name": m["name"],
                "context_window": m["context_window"]
            }
            for m in KNOWN_MODELS
        ]
    })


async def not_found(request: Request) -> JSONResponse:
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"error": {"message": "Not found", "type": "not_found_error", "code": 404}}
    )


routes = [
    Route("/v1/chat/completions", chat_completions, methods=["POST"]),
    Route("/health", health, methods=["GET"]),
    Route("/v1/models", list_models, methods=["GET"]),
]

app = Starlette(routes=routes, exception_handlers={404: not_found})
