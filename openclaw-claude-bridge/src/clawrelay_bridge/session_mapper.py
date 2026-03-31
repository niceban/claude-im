"""Session mapping between OpenClaw sessions and claude-node sessions."""

import asyncio
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionMapping:
    """Represents a session mapping entry."""
    id: int
    openclaw_session_id: str
    claude_session_id: str
    platform: str
    user_id: str
    created_at: str
    last_active: float
    status: str  # active | paused | archived


class SessionMapper:
    """Manages session mapping between OpenClaw and claude-node."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    openclaw_session_id TEXT UNIQUE NOT NULL,
                    claude_session_id TEXT UNIQUE NOT NULL,
                    platform TEXT DEFAULT '',
                    user_id TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_active REAL NOT NULL,
                    status TEXT DEFAULT 'active'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_openclaw_session
                ON session_mapping(openclaw_session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_claude_session
                ON session_mapping(claude_session_id)
            """)
            conn.commit()
            logger.info(f"[SessionMapper] Database initialized: {self.db_path}")
        finally:
            conn.close()

    @contextmanager
    def _get_conn(self):
        """Get a database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def create_mapping(
        self,
        openclaw_session_id: str,
        claude_session_id: str,
        platform: str = "",
        user_id: str = "",
    ) -> SessionMapping:
        """Create a new session mapping."""
        now = time.time()
        created_at = datetime.now().isoformat()

        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO session_mapping
                (openclaw_session_id, claude_session_id, platform, user_id, created_at, last_active, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (openclaw_session_id, claude_session_id, platform, user_id, created_at, now, "active"))

            mapping_id = cursor.lastrowid
            conn.commit()

        logger.info(f"[SessionMapper] Created mapping: {openclaw_session_id} -> {claude_session_id}")

        return SessionMapping(
            id=mapping_id,
            openclaw_session_id=openclaw_session_id,
            claude_session_id=claude_session_id,
            platform=platform,
            user_id=user_id,
            created_at=created_at,
            last_active=now,
            status="active",
        )

    def get_by_openclaw_session(self, openclaw_session_id: str) -> Optional[SessionMapping]:
        """Get mapping by OpenClaw session ID."""
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT id, openclaw_session_id, claude_session_id, platform, user_id,
                       created_at, last_active, status
                FROM session_mapping
                WHERE openclaw_session_id = ?
            """, (openclaw_session_id,)).fetchone()

            if row:
                return SessionMapping(*row)
        return None

    def get_by_claude_session(self, claude_session_id: str) -> Optional[SessionMapping]:
        """Get mapping by claude-node session ID."""
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT id, openclaw_session_id, claude_session_id, platform, user_id,
                       created_at, last_active, status
                FROM session_mapping
                WHERE claude_session_id = ?
            """, (claude_session_id,)).fetchone()

            if row:
                return SessionMapping(*row)
        return None

    def update_last_active(self, openclaw_session_id: str) -> bool:
        """Update last_active timestamp for a session."""
        now = time.time()
        with self._get_conn() as conn:
            cursor = conn.execute("""
                UPDATE session_mapping
                SET last_active = ?
                WHERE openclaw_session_id = ?
            """, (now, openclaw_session_id))
            conn.commit()
            return cursor.rowcount > 0

    def archive_session(self, openclaw_session_id: str) -> bool:
        """Mark a session as archived."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                UPDATE session_mapping
                SET status = 'archived'
                WHERE openclaw_session_id = ?
            """, (openclaw_session_id,))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"[SessionMapper] Archived session: {openclaw_session_id}")
                return True
        return False

    def delete_mapping(self, openclaw_session_id: str) -> bool:
        """Delete a session mapping."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                DELETE FROM session_mapping
                WHERE openclaw_session_id = ?
            """, (openclaw_session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_active_mappings(self) -> list[SessionMapping]:
        """List all active session mappings."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT id, openclaw_session_id, claude_session_id, platform, user_id,
                       created_at, last_active, status
                FROM session_mapping
                WHERE status = 'active'
                ORDER BY last_active DESC
            """).fetchall()

            return [SessionMapping(*row) for row in rows]
