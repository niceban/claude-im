"""
会话管理器模块

管理 relay_session_id 的持久化和会话历史：
- SQLite：存储 relay_session_id（进程重启后不丢失）
- JSONL：存储每条会话的消息历史
- 2小时超时自动过期
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── 模块级路径配置 ────────────────────────────────────────────────────────

def _get_project_root() -> Path:
    return Path(__file__).parent.parent.parent

# sessions/ 目录：包含 sessions.db 和 jsonl/ 子目录
_SESSIONS_ROOT: Path = _get_project_root() / "sessions"
_SQLITE_DB: Path = _SESSIONS_ROOT / "sessions.db"
_JSONL_DIR: Path = _SESSIONS_ROOT / "jsonl"

# 模块级内存缓存（加速热路径，SQLite 作持久化兜底）
_sessions_cache: dict[str, dict] = {}
_cache_loaded: bool = False
_cache_loaded_lock = asyncio.Lock()


def _init_storage():
    """初始化目录和 SQLite 表"""
    _SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    _JSONL_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_SQLITE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            key         TEXT PRIMARY KEY,   -- "{bot_key}_{user_id}"
            relay_id    TEXT NOT NULL,       -- relay_session_id (UUID)
            last_active REAL NOT NULL         -- time.monotonic() 戳
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_meta (
            relay_id   TEXT PRIMARY KEY,
            bot_key    TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logger.info("[SessionManager] SQLite 初始化完成: %s", _SQLITE_DB)


def _ensure_cache_loaded_sync():
    """同步版：从 SQLite 加载缓存（供 startup 调用）"""
    global _sessions_cache, _cache_loaded
    if _cache_loaded:
        return
    _init_storage()
    try:
        conn = sqlite3.connect(str(_SQLITE_DB))
        rows = conn.execute(
            "SELECT key, relay_id, last_active FROM sessions"
        ).fetchall()
        now = time.monotonic()
        for key, relay_id, last_active in rows:
            if now - last_active < 2 * 3600:  # 2h 过滤
                _sessions_cache[key] = {
                    "relay_session_id": relay_id,
                    "last_active": last_active,
                }
        conn.close()
        _cache_loaded = True
        logger.info("[SessionManager] 从 SQLite 加载了 %d 条会话缓存", len(_sessions_cache))
    except Exception as e:
        logger.warning("[SessionManager] 从 SQLite 加载缓存失败: %s", e)


class SessionManager:
    """会话管理器 - SQLite + JSONL 持久化"""

    SESSION_TIMEOUT_SECONDS = 2 * 3600  # 2 hours

    def __init__(self):
        _ensure_cache_loaded_sync()

    # ── 核心会话 ID 操作 ───────────────────────────────────────────────────

    async def get_relay_session_id(self, bot_key: str, user_id: str) -> str:
        key = f"{bot_key}_{user_id}"
        entry = _sessions_cache.get(key)

        if not entry:
            return ""

        elapsed = time.monotonic() - entry["last_active"]
        if elapsed > self.SESSION_TIMEOUT_SECONDS:
            logger.info("会话已超时: %s (%.1f小时前)", key, elapsed / 3600)
            if key in _sessions_cache:
                del _sessions_cache[key]
            self._db_delete(key)
            return ""

        return entry.get("relay_session_id", "")

    async def save_relay_session_id(self, bot_key: str, user_id: str, relay_session_id: str):
        key = f"{bot_key}_{user_id}"
        now = time.monotonic()
        entry = {
            "relay_session_id": relay_session_id,
            "last_active": now,
        }
        _sessions_cache[key] = entry

        # 落 SQLite
        conn = sqlite3.connect(str(_SQLITE_DB))
        try:
            conn.execute("""
                INSERT OR REPLACE INTO sessions (key, relay_id, last_active)
                VALUES (?, ?, ?)
            """, (key, relay_session_id, now))
            # 记录 meta（用于 list 时快速查）
            conn.execute("""
                INSERT OR IGNORE INTO session_meta (relay_id, bot_key, user_id, created_at)
                VALUES (?, ?, ?, ?)
            """, (relay_session_id, bot_key, user_id, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()

    async def clear_session(self, bot_key: str, user_id: str):
        key = f"{bot_key}_{user_id}"
        _sessions_cache.pop(key, None)
        self._db_delete(key)
        logger.info("清空会话: %s", key)

    def _db_delete(self, key: str):
        try:
            conn = sqlite3.connect(str(_SQLITE_DB))
            conn.execute("DELETE FROM sessions WHERE key = ?", (key,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("[SessionManager] 删除 session 失败: %s", e)

    # ── JSONL 消息历史 ─────────────────────────────────────────────────────

    def _jsonl_path(self, relay_session_id: str) -> Path:
        return _JSONL_DIR / f"{relay_session_id}.jsonl"

    def append_to_jsonl(self, relay_session_id: str, entry: dict):
        """追加一条消息到会话历史 JSONL"""
        path = self._jsonl_path(relay_session_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_jsonl(self, relay_session_id: str, limit: int = 50) -> list[dict]:
        """读取会话历史（最近 limit 条）"""
        path = self._jsonl_path(relay_session_id)
        if not path.exists():
            return []
        entries = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries[-limit:] if limit else entries

    # ── Session Panel API ─────────────────────────────────────────────────

    def list_active_sessions(self, bot_key: Optional[str] = None) -> list[dict]:
        """列出活跃会话（供 admin API 使用）"""
        sessions = []
        now = time.monotonic()
        for key, entry in list(_sessions_cache.items()):
            relay_id = entry.get("relay_session_id", "")
            last_active = entry.get("last_active", 0)
            if now - last_active > self.SESSION_TIMEOUT_SECONDS:
                continue
            parts = key.rsplit("_", 1)
            bk = parts[0] if parts else key
            uid = parts[1] if len(parts) > 1 else ""
            if bot_key and bk != bot_key:
                continue
            history_path = self._jsonl_path(relay_id)
            msg_count = 0
            if history_path.exists():
                with open(history_path, encoding="utf-8") as f:
                    msg_count = sum(1 for _ in f)
            sessions.append({
                "relay_session_id": relay_id,
                "bot_key": bk,
                "user_id": uid,
                "last_active": datetime.fromtimestamp(
                    now - (now - last_active), tz=None
                ).isoformat(),
                "message_count": msg_count,
                "active": True,
            })
        return sessions

    # ── 启动时加载 ────────────────────────────────────────────────────────

    async def _ensure_cache_loaded(self):
        """异步版：确保缓存已从 SQLite 加载"""
        global _cache_loaded
        async with _cache_loaded_lock:
            if _cache_loaded:
                return
            _ensure_cache_loaded_sync()
