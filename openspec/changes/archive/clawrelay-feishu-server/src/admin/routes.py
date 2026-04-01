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
import uuid
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


@router.patch("/admin/sessions/{relay_session_id}")
async def rename_admin_session(relay_session_id: str, request: dict):
    """重命名指定会话（仅 Admin 可用）"""
    new_name = request.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="会话名称不能为空")

    _SQLITE_DB = Path(__file__).parent.parent.parent / "sessions" / "sessions.db"
    _SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3
    conn = sqlite3.connect(str(_SQLITE_DB))
    try:
        # 确保 name 列存在（向后兼容）
        conn.execute("ALTER TABLE admin_session_meta ADD COLUMN name TEXT")

        conn.execute(
            "UPDATE admin_session_meta SET name = ? WHERE relay_id = ?",
            (new_name, relay_session_id),
        )
        conn.commit()

        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="会话不存在")
    finally:
        conn.close()

    return {"relay_session_id": relay_session_id, "name": new_name}


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


# ─── Admin Claude Chat（独立于 Feishu 的会话管理）────────────────────────────

_admin_adapter = None
_admin_adapter_lock = threading.Lock()
_ADMIN_BOT_KEY = "_admin_internal"


def _get_admin_adapter():
    """获取 Admin 专用 ClaudeNodeAdapter（单例，按需创建）"""
    global _admin_adapter
    if _admin_adapter is not None:
        return _admin_adapter

    with _admin_adapter_lock:
        if _admin_adapter is not None:
            return _admin_adapter

        try:
            from config.bot_config import BotConfigManager
            from src.adapters.claude_node_adapter import ClaudeNodeAdapter
        except Exception as e:
            logger.error(f"[AdminAPI] 无法加载依赖: {e}")
            raise HTTPException(status_code=500, detail="服务初始化失败，请检查配置")

        cfg = BotConfigManager()
        bots = cfg.get_all_bots()
        if not bots:
            raise HTTPException(status_code=500, detail="未配置任何机器人")

        # 使用第一个 bot 的配置作为 admin adapter 的配置
        first_bot = next(iter(bots.values()))
        _admin_adapter = ClaudeNodeAdapter(
            model=first_bot.model,
            working_dir=first_bot.working_dir,
            env_vars={},  # admin 会话不继承 bot 环境变量
            system_prompt=first_bot.system_prompt or "",
        )
        logger.info("[AdminAPI] ClaudeNodeAdapter 已初始化（model=%s, dir=%s）",
                     first_bot.model, first_bot.working_dir)
        return _admin_adapter


@router.post("/admin/sessions")
async def create_admin_session(
    request: dict,
):
    """在 dashboard 新建一个内部会话，返回 relay_session_id。

    Body:
        message: 初始消息内容（可选）
        bot_key: 使用哪个机器人配置（可选，默认第一个）
        owner_id: 创建者 ID（可选）
    """
    mgr = _get_session_manager()
    if mgr is None:
        raise HTTPException(status_code=500, detail="SessionManager 不可用")

    relay_session_id = str(uuid.uuid4())
    effective_key = f"{_ADMIN_BOT_KEY}_admin_{relay_session_id}"
    owner_id = request.get("owner_id", "admin")
    bot_key = request.get("bot_key", _ADMIN_BOT_KEY)

    # 保存 session 记录
    await mgr.save_relay_session_id(bot_key, effective_key, relay_session_id)

    # 记录 meta（包含 owner）
    import sqlite3
    from pathlib import Path
    _SQLITE_DB = Path(__file__).parent.parent.parent / "sessions" / "sessions.db"
    _SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_SQLITE_DB))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_session_meta (
                relay_id    TEXT PRIMARY KEY,
                owner_id    TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO admin_session_meta (relay_id, owner_id, created_at)
            VALUES (?, ?, ?)
        """, (relay_session_id, owner_id, datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()

    # 如果有初始消息，立即处理
    message = request.get("message", "").strip()
    if message:
        # 在后台处理首条消息
        logger.info(f"[AdminAPI] 创建后台任务处理初始消息: {relay_session_id}")
        asyncio.create_task(_process_admin_message(
            relay_session_id=relay_session_id,
            effective_key=effective_key,
            bot_key=bot_key,
            message=message,
            owner_id=owner_id,
        ))

    return {
        "relay_session_id": relay_session_id,
        "effective_key": effective_key,
        "status": "processing" if message else "ready",
        "timestamp": datetime.now().isoformat(),
    }


async def _process_admin_message(
    relay_session_id: str,
    effective_key: str,
    bot_key: str,
    message: str,
    owner_id: str,
):
    """后台处理 admin 会话的首条消息"""
    logger.info(f"[AdminAPI] _process_admin_message 开始: {relay_session_id}, message={message[:50]}")
    try:
        adapter = _get_admin_adapter()
        logger.info(f"[AdminAPI] 获取到 adapter")
        session_lock = await adapter._get_session_lock(relay_session_id)
        logger.info(f"[AdminAPI] 获取到 session_lock")

        try:
            await asyncio.wait_for(session_lock.acquire(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning(f"[AdminAPI] 无法获取 session lock: {relay_session_id}")
            return

        try:
            from src.core.claude_relay_orchestrator import SECURITY_SYSTEM_PROMPT
            effective_prompt = SECURITY_SYSTEM_PROMPT + f"\n[当前会话] FEISHU_CHAT_ID={effective_key}"
            messages = [{"role": "user", "content": message}]
            logger.info(f"[AdminAPI] 开始 stream_chat, session_id={relay_session_id}")

            accumulated_text = ""
            async for event in adapter.stream_chat(
                messages, effective_prompt,
                session_id=relay_session_id, resume="",
            ):
                if hasattr(event, 'text'):
                    accumulated_text += event.text
            logger.info(f"[AdminAPI] stream_chat 完成, text_len={len(accumulated_text)}, session={relay_session_id}")

            if not accumulated_text.strip():
                accumulated_text = "AI 已完成处理，但未生成文本回复。"

            mgr = _get_session_manager()
            if mgr:
                mgr.append_to_jsonl(relay_session_id, {"role": "user", "content": message})
                mgr.append_to_jsonl(relay_session_id, {"role": "assistant", "content": accumulated_text})

            # 推送到 WebSocket 客户端
            _push_ws_event(relay_session_id, {
                "type": "message",
                "role": "assistant",
                "content": accumulated_text,
                "timestamp": datetime.now().isoformat(),
            })
            logger.info(f"[AdminAPI] 处理完成")

        finally:
            session_lock.release()

    except Exception as e:
        logger.error(f"[AdminAPI] 处理 admin 消息失败: {e}", exc_info=True)
        _push_ws_event(relay_session_id, {
            "type": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


@router.post("/admin/sessions/{relay_session_id}/messages")
async def send_admin_message(
    relay_session_id: str,
    request: dict,
):
    """向指定会话发送消息（流式返回）"""
    message = request.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    mgr = _get_session_manager()
    if mgr is None:
        raise HTTPException(status_code=500, detail="SessionManager 不可用")

    # 写用户消息到 JSONL
    mgr.append_to_jsonl(relay_session_id, {"role": "user", "content": message})

    # 立即推送用户消息事件（让前端立即看到自己的消息）
    _push_ws_event(relay_session_id, {
        "type": "message",
        "role": "user",
        "content": message,
        "timestamp": datetime.now().isoformat(),
    })

    # 后台异步处理
    asyncio.create_task(_process_admin_message_stream(
        relay_session_id=relay_session_id,
        message=message,
    ))

    return {"status": "processing", "timestamp": datetime.now().isoformat()}


async def _process_admin_message_stream(relay_session_id: str, message: str):
    """后台流式处理消息，通过 WebSocket 推送"""
    try:
        adapter = _get_admin_adapter()
        session_lock = await adapter._get_session_lock(relay_session_id)

        try:
            await asyncio.wait_for(session_lock.acquire(), timeout=10.0)
        except asyncio.TimeoutError:
            _push_ws_event(relay_session_id, {
                "type": "error", "error": "会话忙，请稍后重试"
            })
            return

        try:
            from src.core.claude_relay_orchestrator import SECURITY_SYSTEM_PROMPT
            sessions = adapter._controllers
            ctrl = adapter._controllers.get(relay_session_id)
            effective_key = relay_session_id
            effective_prompt = SECURITY_SYSTEM_PROMPT + f"\n[当前会话] FEISHU_CHAT_ID={effective_key}"
            messages = [{"role": "user", "content": message}]

            accumulated_text = ""
            async for event in adapter.stream_chat(
                messages, effective_prompt,
                session_id=relay_session_id, resume=relay_session_id,
            ):
                if hasattr(event, 'text'):
                    accumulated_text += event.text
                    _push_ws_event(relay_session_id, {
                        "type": "delta",
                        "content": event.text,
                        "timestamp": datetime.now().isoformat(),
                    })

            if not accumulated_text.strip():
                accumulated_text = "AI 已完成处理，但未生成文本回复。"

            mgr = _get_session_manager()
            if mgr:
                mgr.append_to_jsonl(relay_session_id, {"role": "assistant", "content": accumulated_text})

            _push_ws_event(relay_session_id, {
                "type": "done",
                "content": accumulated_text,
                "timestamp": datetime.now().isoformat(),
            })

        finally:
            session_lock.release()

    except Exception as e:
        logger.error(f"[AdminAPI] 流式处理失败: {e}", exc_info=True)
        _push_ws_event(relay_session_id, {
            "type": "error", "error": str(e)
        })


def _push_ws_event(session_id: str, event: dict):
    """推送事件到订阅该 session 的 WebSocket 客户端"""
    with _ws_clients_lock:
        clients = _ws_clients.get(session_id, [])
        disconnected = []
        for ws in clients:
            try:
                ws.send_json(event)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            clients.remove(ws)


@router.get("/admin/sessions/{relay_session_id}/history")
async def get_admin_session_history(relay_session_id: str, limit: int = 50):
    """获取 admin 会话的历史消息"""
    mgr = _get_session_manager()
    if mgr is None:
        raise HTTPException(status_code=500, detail="SessionManager 不可用")
    entries = mgr.read_jsonl(relay_session_id, limit=limit)
    return {"history": entries, "timestamp": datetime.now().isoformat()}


@router.get("/admin/sessions")
async def list_admin_sessions(owner_id: Optional[str] = None):
    """列出所有 admin 会话（可选按 owner_id 过滤）"""
    import sqlite3
    from pathlib import Path
    _SQLITE_DB = Path(__file__).parent.parent.parent / "sessions" / "sessions.db"
    if not _SQLITE_DB.exists():
        return {"sessions": [], "total": 0, "timestamp": datetime.now().isoformat()}

    conn = sqlite3.connect(str(_SQLITE_DB))
    try:
        if owner_id:
            rows = conn.execute("""
                SELECT m.relay_id, m.owner_id, m.created_at,
                       s.last_active
                FROM admin_session_meta m
                LEFT JOIN sessions s ON s.relay_id = m.relay_id
                WHERE m.owner_id = ?
                ORDER BY m.created_at DESC
            """, (owner_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT m.relay_id, m.owner_id, m.created_at,
                       s.last_active
                FROM admin_session_meta m
                LEFT JOIN sessions s ON s.relay_id = m.relay_id
                ORDER BY m.created_at DESC
            """).fetchall()
    finally:
        conn.close()

    sessions = []
    for row in rows:
        sessions.append({
            "relay_session_id": row[0],
            "owner_id": row[1],
            "created_at": row[2],
            "last_active": row[3] or "",
        })
    return {
        "sessions": sessions,
        "total": len(sessions),
        "timestamp": datetime.now().isoformat(),
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
