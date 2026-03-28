"""
Admin API Server

独立 FastAPI 进程（端口 8080），提供：
- GET /metrics         — Prometheus 指标
- GET /sessions       — 活跃会话列表
- GET /sessions/{id}  — 单会话详情
- WebSocket /ws/{session_id} — 实时流式推送
- PATCH /config/{bot_key} — 热更新 system_prompt
- GET /health         — 健康检查

与主 bot 进程通过共享 SessionManager（SQLite）通信。
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# ─── 状态共享 ────────────────────────────────────────────────────────────────

# 全局回调：用于推送实时事件到 WebSocket 客户端
_ws_clients: dict[str, list[WebSocket]] = {}
_ws_clients_lock = threading.Lock()


def broadcast_session_event(session_id: str, event_type: str, payload: dict):
    """广播会话事件到所有订阅该 session 的 WebSocket 客户端"""
    with _ws_clients_lock:
        clients = _ws_clients.get(session_id, [])
        disconnected = []
        for ws in clients:
            try:
                import json
                ws.send_json({"type": event_type, "payload": payload, "ts": datetime.now().isoformat()})
            except Exception:
                disconnected.append(ws)
        # 清理断开的客户端
        for ws in disconnected:
            clients.remove(ws)


# ─── FastAPI App ─────────────────────────────────────────────────────────────

_admin_app: Optional[FastAPI] = None


def create_admin_app(session_store_ref=None) -> FastAPI:
    """创建 Admin API app（延迟导入避免循环依赖）"""
    global _admin_app

    app = FastAPI(
        title="ClaweRelay Admin API",
        version="1.0.0",
        description="会话管理、Metrics、热更新",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 挂载子路由 ────────────────────────────────────────────────────────
    from . import routes
    app.include_router(routes.router)

    _admin_app = app
    return app


def get_admin_app() -> Optional[FastAPI]:
    return _admin_app
