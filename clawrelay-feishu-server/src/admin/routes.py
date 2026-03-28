"""
Admin API Routes
"""

import asyncio
import logging
import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["admin"])

# 全局 WebSocket 客户端
_ws_clients: dict[str, list[WebSocket]] = {}
_ws_clients_lock = threading.Lock()


# ─── Helpers ────────────────────────────────────────────────────────────────

def _get_session_manager():
    """获取 SessionManager 实例（通过路径导入避免循环依赖）"""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    try:
        from src.core.session_manager import SessionManager
        return SessionManager()
    except Exception as e:
        logger.warning("无法加载 SessionManager: %s", e)
        return None


# ─── Prometheus Metrics ─────────────────────────────────────────────────────

@router.get("/metrics")
async def metrics():
    """Prometheus 指标端点"""
    from fastapi.responses import Response
    from src.core.metrics import MetricsCollector
    data, content_type = MetricsCollector.metrics()
    return Response(content=data, media_type=content_type)


# ─── Session APIs ───────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(bot_key: Optional[str] = None):
    """列出所有活跃会话"""
    mgr = _get_session_manager()
    if mgr is None:
        raise HTTPException(status_code=500, detail="SessionManager 不可用")

    sessions = mgr.list_active_sessions(bot_key=bot_key)
    return {
        "total": len(sessions),
        "sessions": sessions,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/sessions/{relay_session_id}")
async def get_session_detail(relay_session_id: str):
    """获取单个会话详情（含 JSONL 历史）"""
    mgr = _get_session_manager()
    if mgr is None:
        raise HTTPException(status_code=500, detail="SessionManager 不可用")

    entries = mgr.read_jsonl(relay_session_id, limit=50)
    sessions = mgr.list_active_sessions()
    session_info = next((s for s in sessions if s["relay_session_id"] == relay_session_id), None)

    if not session_info and not entries:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "session": session_info or {},
        "history": entries,
        "timestamp": datetime.now().isoformat(),
    }


@router.delete("/sessions/{relay_session_id}")
async def kill_session(relay_session_id: str):
    """强制终止指定会话"""
    # TODO: 通知 claude_node_adapter 停止对应的 controller
    raise HTTPException(status_code=501, detail="会话终止功能待实现")


# ─── Config APIs ────────────────────────────────────────────────────────────

@router.get("/config/{bot_key}")
async def get_bot_config(bot_key: str):
    """获取 bot 配置（敏感字段除外）"""
    from config.bot_config import BotConfigManager
    mgr = BotConfigManager()
    bot = mgr.bots.get(bot_key)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot 不存在")

    # 不返回敏感字段
    return {
        "bot_key": bot.bot_key,
        "description": bot.description,
        "model": bot.model,
        "allowed_users": bot.allowed_users,
        "allowed_tools": bot.allowed_tools,
        "max_concurrent_sessions": bot.max_concurrent_sessions,
        "system_prompt": bot.system_prompt[:500] if bot.system_prompt else "",
        "working_dir": bot.working_dir,
    }


@router.patch("/config/{bot_key}/system_prompt")
async def update_system_prompt(bot_key: str, body: dict):
    """热更新 system_prompt（不重启进程）"""
    new_prompt = body.get("system_prompt", "")
    if not new_prompt:
        raise HTTPException(status_code=400, detail="system_prompt 不能为空")

    # 通知主进程重载配置（通过发送 SIGUSR1 信号）
    pid_file = Path.home() / "clawrelay-feishu-server" / "bot.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGUSR1)
            logger.info("[AdminAPI] 发送 SIGUSR1 到 %d 重载 system_prompt", pid)
        except (ValueError, ProcessLookupError, PermissionError) as e:
            logger.warning("[AdminAPI] 无法发送 SIGUSR1: %s", e)
            raise HTTPException(status_code=500, detail="无法重载配置：进程不存在或无权限")

    return {"status": "ok", "bot_key": bot_key, "message": "配置已更新，需重新发消息生效"}


# ─── Health ────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """健康检查"""
    mgr = _get_session_manager()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "session_manager": "ok" if mgr else "error",
    }


# ─── WebSocket 实时推送 ─────────────────────────────────────────────────────

@router.websocket("/ws/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str):
    """WebSocket 订阅指定会话的实时事件"""
    await websocket.accept()

    with _ws_clients_lock:
        if session_id not in _ws_clients:
            _ws_clients[session_id] = []
        _ws_clients[session_id].append(websocket)

    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        })

        # 保持连接，接收客户端消息（或心跳）
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                # 心跳：客户端发送 ping，服务器回复 pong
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                try:
                    await websocket.send_json({"type": "heartbeat", "timestamp": datetime.now().isoformat()})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        with _ws_clients_lock:
            if session_id in _ws_clients and websocket in _ws_clients[session_id]:
                _ws_clients[session_id].remove(websocket)
