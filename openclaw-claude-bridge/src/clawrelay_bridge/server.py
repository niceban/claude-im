"""Bridge Server - HTTP API wrapper for claude-node."""

import asyncio
import concurrent.futures
import logging
import uuid
from datetime import datetime
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from clawrelay_bridge.config import Config
from clawrelay_bridge.session_mapper import SessionMapper
from clawrelay_bridge.health_monitor import HealthMonitor
from clawrelay_bridge.fallback_manager import FallbackManager, FallbackState

logger = logging.getLogger(__name__)

MAX_WORKERS = 5  # Thread pool max workers for server tasks

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=1_000_000)  # 1MB limit


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage] = Field(min_length=1)  # Require at least 1 message
    max_tokens: Optional[int] = 8192
    stream: Optional[bool] = False


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    choices: List[ChatCompletionChoice]


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 1700000000
    owned_by: str = "claude"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


class HealthResponse(BaseModel):
    status: str
    claude_node: str
    fallback_state: str
    timestamp: str
    session_count: int


# ─── BridgeServer ──────────────────────────────────────────────────────────────

class BridgeServer:
    """
    HTTP API wrapper for claude-node.

    Exposes OpenAI-compatible endpoints:
    - POST /v1/chat/completions
    - GET /v1/models
    - GET /health
    """

    def __init__(self, config: Config):
        self.config = config

        # Initialize components
        self.session_mapper = SessionMapper(config.db_path)
        self.health_monitor = HealthMonitor(
            check_interval=config.health_check_interval,
            failure_threshold=config.fallback_failure_threshold,
            success_threshold=config.fallback_success_threshold,
        )
        self.fallback_manager = FallbackManager(
            failure_threshold=config.fallback_failure_threshold,
            success_threshold=config.fallback_success_threshold,
            on_activate=self._on_fallback_activate,
            on_deactivate=self._on_fallback_deactivate,
        )

        # Connect health monitor to fallback manager
        self.health_monitor.on_become_healthy = self.fallback_manager.report_healthy
        self.health_monitor.on_become_unhealthy = self.fallback_manager.report_unhealthy

        # claude-node adapter - lazy initialization
        self._claude_adapter = None
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

        # FastAPI app
        self.app = FastAPI(title="clawrelay-bridge")
        self._setup_routes()

        # Server reference
        self._server = None

    def _setup_routes(self):
        """Set up FastAPI routes."""
        self.app.add_api_route("/v1/chat/completions", self.chat_completions, methods=["POST"])
        self.app.add_api_route("/v1/models", self.list_models, methods=["GET"])
        self.app.add_api_route("/health", self.health, methods=["GET"])

    def _on_fallback_activate(self):
        """Called when fallback mode is activated."""
        logger.warning("[BridgeServer] FALLBACK MODE ACTIVATED - OpenClaw should activate")

    def _on_fallback_deactivate(self):
        """Called when fallback mode is deactivated."""
        logger.info("[BridgeServer] Fallback deactivated - resuming normal operation")

    def _get_claude_adapter(self):
        """Get or create claude-node adapter."""
        if self._claude_adapter is None:
            # Import from local copy of ClaudeNodeAdapter
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from claude_node_adapter import ClaudeNodeAdapter

            self._claude_adapter = ClaudeNodeAdapter(
                model=self.config.claude_model,
                working_dir=self.config.claude_working_dir,
                env_vars=self.config.claude_env_vars,
            )
            self.health_monitor.set_claude_adapter(self._claude_adapter)

        return self._claude_adapter

    def _get_openclaw_session_id(self, request: Request) -> str:
        """
        Get OpenClaw session ID from request.

        Tries to get from:
        1. X-OpenClaw-Session-ID header
        2. X-Session-ID header
        3. Generate a new UUID if not provided
        """
        session_id = (
            request.headers.get("X-OpenClaw-Session-ID")
            or request.headers.get("X-Session-ID")
        )
        if session_id:
            return session_id

        # Generate new session ID
        return str(uuid.uuid4())

    async def chat_completions(self, request: Request, body: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        Handle chat completion request.

        This is a blocking v1 implementation - no streaming.
        """
        # Check if fallback mode is active - reject requests if claude-node is down
        if self.fallback_manager.is_fallback_active:
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable - claude-node is not available. OpenClaw fallback mode active."
            )

        # Get session ID from headers or generate new one
        openclaw_session_id = self._get_openclaw_session_id(request)
        mapping = self.session_mapper.get_by_openclaw_session(openclaw_session_id)

        if mapping is None:
            # Create new claude-node session
            claude_session_id = str(uuid.uuid4())
            mapping = self.session_mapper.create_mapping(
                openclaw_session_id=openclaw_session_id,
                claude_session_id=claude_session_id,
            )

        # Update last active
        self.session_mapper.update_last_active(openclaw_session_id)

        # Build messages for claude-node
        messages = [{"role": m.role, "content": m.content} for m in body.messages]

        try:
            # Get response using thread pool
            loop = asyncio.get_event_loop()
            response_text = await loop.run_in_executor(
                self._thread_pool,
                self._blocking_chat_sync,
                messages,
                mapping.claude_session_id,
            )

            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                model=body.model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=response_text),
                        finish_reason="stop",
                    )
                ],
            )

        except Exception as e:
            logger.error(f"[BridgeServer] Chat completion failed: {e}", exc_info=True)
            # Return generic error message - do not leak internal details
            raise HTTPException(
                status_code=500,
                detail="An error occurred while processing your request. Please try again."
            )

    def _blocking_chat_sync(self, messages: List[dict], session_id: str) -> str:
        """Run blocking chat in thread pool (synchronous)."""
        adapter = self._get_claude_adapter()

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            text_parts = []

            async def collect():
                async for event in adapter.stream_chat(
                    messages=messages,
                    session_id=session_id,
                ):
                    # Collect text events (blocking v1 just returns final text)
                    if hasattr(event, 'text'):
                        text_parts.append(event.text)

            loop.run_until_complete(collect())
            return "".join(text_parts)
        finally:
            loop.close()

    async def list_models(self) -> ModelListResponse:
        """Return list of available models."""
        return ModelListResponse(
            data=[
                ModelInfo(
                    id=self.config.claude_model,
                    owned_by="anthropic",
                ),
            ]
        )

    async def health(self) -> HealthResponse:
        """Return health status."""
        health_state = self.health_monitor.get_status()
        session_count = len(self.session_mapper.list_active_mappings())

        return HealthResponse(
            status=health_state.status.value,
            claude_node="connected" if health_state.claude_node_connected else "disconnected",
            fallback_state=self.fallback_manager.state.value,
            timestamp=datetime.now().isoformat(),
            session_count=session_count,
        )

    async def start(self):
        """Start the bridge server."""
        # Start health monitor
        self.health_monitor.start()

        # Run FastAPI with uvicorn
        config_uvicorn = uvicorn.Config(
            app=self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
        )
        self._server = uvicorn.Server(config_uvicorn)

        logger.info(f"[BridgeServer] Starting on {self.config.host}:{self.config.port}")
        await self._server.serve()

    def stop(self):
        """Stop the bridge server."""
        logger.info("[BridgeServer] Stopping...")
        if self._claude_adapter:
            self._claude_adapter.stop()

        # Wait for pending tasks to complete
        self._thread_pool.shutdown(wait=True)
        asyncio.create_task(self.health_monitor.stop())
