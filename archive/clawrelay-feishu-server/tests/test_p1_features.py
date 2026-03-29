"""
测试 P1 功能：
1. Session 持久化（JSONL + SQLite）
2. 错误码区分（_friendly_error）
3. 流式卡片回调（thinking card）
4. MCP 失败检测
"""

import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.bot_config import BotConfig


class TestFriendlyError(unittest.TestCase):
    """测试 _friendly_error 错误码区分"""

    def _get_friendly_error(self, msg: str) -> str:
        from src.transport.message_dispatcher import _friendly_error
        return _friendly_error(Exception(msg))

    def test_401_unauthorized(self):
        result = self._get_friendly_error("401 Unauthorized")
        self.assertIn("认证", result)

    def test_403_forbidden(self):
        result = self._get_friendly_error("403 Forbidden")
        self.assertIn("拒绝", result)

    def test_429_rate_limit(self):
        result = self._get_friendly_error("429 rate limit exceeded")
        self.assertIn("频繁", result)

    def test_500_internal_error(self):
        result = self._get_friendly_error("500 Internal Server Error")
        self.assertIn("异常", result)

    def test_502_bad_gateway(self):
        result = self._get_friendly_error("502 Bad Gateway")
        self.assertIn("不可用", result)

    def test_timeout(self):
        result = self._get_friendly_error("timeout error")
        self.assertIn("超时", result)

    def test_generic_error(self):
        result = self._get_friendly_error("some random error")
        self.assertIn("出错", result)

    def test_connection_error(self):
        result = self._get_friendly_error("[Claude] Connection error")
        self.assertIn("Claude 服务", result)

    def test_claude_http_error(self):
        result = self._get_friendly_error("[Claude] HTTP 500")
        self.assertIn("Claude 服务", result)


class TestSessionPersistence(unittest.TestCase):
    """测试 SessionManager JSONL + SQLite 持久化"""

    def test_save_and_get_session(self):
        import tempfile
        from pathlib import Path

        # 用临时目录模拟
        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_root = Path(tmpdir) / "sessions"
            sessions_root.mkdir()

            # Mock SQLite 路径
            import src.core.session_manager as sm
            original_root = sm._SESSIONS_ROOT
            original_db = sm._SQLITE_DB
            original_jsonl = sm._JSONL_DIR

            sm._SESSIONS_ROOT = sessions_root
            sm._SQLITE_DB = sessions_root / "test.db"
            sm._JSONL_DIR = sessions_root / "jsonl"
            sm._JSONL_DIR.mkdir()

            try:
                # 重建 SessionManager（会初始化）
                mgr = sm.SessionManager()
                mgr._ensure_cache_loaded()

                # 保存 session
                asyncio.get_event_loop().run_until_complete(
                    mgr.save_relay_session_id("bot1", "user1", "relay_session_abc")
                )

                # 读取 session
                result = asyncio.get_event_loop().run_until_complete(
                    mgr.get_relay_session_id("bot1", "user1")
                )
                self.assertEqual(result, "relay_session_abc")

                # JSONL 写入
                mgr.append_to_jsonl("relay_session_abc", {"role": "user", "content": "hello"})
                path = sm._JSONL_DIR / "relay_session_abc.jsonl"
                self.assertTrue(path.exists())

            finally:
                sm._SESSIONS_ROOT = original_root
                sm._SQLITE_DB = original_db
                sm._JSONL_DIR = original_jsonl

    def test_list_active_sessions(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_root = Path(tmpdir) / "sessions"
            sessions_root.mkdir()

            import src.core.session_manager as sm
            original_root = sm._SESSIONS_ROOT
            original_db = sm._SQLITE_DB
            original_jsonl = sm._JSONL_DIR

            sm._SESSIONS_ROOT = sessions_root
            sm._SQLITE_DB = sessions_root / "test.db"
            sm._JSONL_DIR = sessions_root / "jsonl"
            sm._JSONL_DIR.mkdir()

            try:
                mgr = sm.SessionManager()
                mgr._ensure_cache_loaded()

                asyncio.get_event_loop().run_until_complete(
                    mgr.save_relay_session_id("bot1", "user1", "relay_1")
                )
                asyncio.get_event_loop().run_until_complete(
                    mgr.save_relay_session_id("bot1", "user2", "relay_2")
                )

                sessions = mgr.list_active_sessions(bot_key="bot1")
                self.assertEqual(len(sessions), 2)
                relay_ids = {s["relay_session_id"] for s in sessions}
                self.assertEqual(relay_ids, {"relay_1", "relay_2"})

            finally:
                sm._SESSIONS_ROOT = original_root
                sm._SQLITE_DB = original_db
                sm._JSONL_DIR = original_jsonl

    def test_clear_session(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_root = Path(tmpdir) / "sessions"
            sessions_root.mkdir()

            import src.core.session_manager as sm
            original_root = sm._SESSIONS_ROOT
            original_db = sm._SQLITE_DB
            original_jsonl = sm._JSONL_DIR

            sm._SESSIONS_ROOT = sessions_root
            sm._SQLITE_DB = sessions_root / "test.db"
            sm._JSONL_DIR = sessions_root / "jsonl"
            sm._JSONL_DIR.mkdir()

            try:
                mgr = sm.SessionManager()
                mgr._ensure_cache_loaded()

                asyncio.get_event_loop().run_until_complete(
                    mgr.save_relay_session_id("bot1", "user1", "relay_1")
                )
                result = asyncio.get_event_loop().run_until_complete(
                    mgr.get_relay_session_id("bot1", "user1")
                )
                self.assertEqual(result, "relay_1")

                asyncio.get_event_loop().run_until_complete(
                    mgr.clear_session("bot1", "user1")
                )
                result = asyncio.get_event_loop().run_until_complete(
                    mgr.get_relay_session_id("bot1", "user1")
                )
                self.assertEqual(result, "")

            finally:
                sm._SESSIONS_ROOT = original_root
                sm._SQLITE_DB = original_db
                sm._JSONL_DIR = original_jsonl


class TestMCPFallback(unittest.TestCase):
    """测试 MCP 不可用检测"""

    def test_is_mcp_unavailable_patterns(self):
        from src.adapters.claude_node_adapter import _is_mcp_unavailable

        self.assertTrue(_is_mcp_unavailable("MCP server is not running"))
        self.assertTrue(_is_mcp_unavailable("connection refused"))
        self.assertTrue(_is_mcp_unavailable("Failed to start MCP server"))
        self.assertTrue(_is_mcp_unavailable("401 Unauthorized"))
        self.assertTrue(_is_mcp_unavailable("auth token missing"))
        self.assertTrue(_is_mcp_unavailable("ECONNREFUSED"))

        self.assertFalse(_is_mcp_unavailable("Hello world"))
        self.assertFalse(_is_mcp_unavailable("normal response text"))


class TestStreamingCallbackSignature(unittest.TestCase):
    """测试流式回调签名兼容性"""

    def test_stream_delta_callback_accepts_three_args(self):
        """_make_stream_delta_callback 返回的回调接受 (text, finish, tool_names)"""
        from src.transport.message_dispatcher import MessageDispatcher

        mock_api = MagicMock()
        mock_api.edit_text = AsyncMock()

        with patch.object(MessageDispatcher, '__init__', lambda self, *args: None):
            dispatcher = MessageDispatcher.__new__(MessageDispatcher)
            dispatcher.feishu_api = mock_api
            dispatcher.bot_key = "test"

            callback = dispatcher._make_stream_delta_callback("msg_id_123")
            # 应该能接受三个参数而不抛 TypeError
            async def test_call():
                await callback("hello", False, ["tool_a", "tool_b"])
            asyncio.get_event_loop().run_until_complete(test_call())

    def test_stream_card_callback_accepts_three_args(self):
        """_make_stream_card_callback 返回的回调接受 (text, finish, tool_names)"""
        from src.transport.message_dispatcher import MessageDispatcher

        mock_api = MagicMock()
        mock_api.send_card = AsyncMock(return_value="card_msg_id")

        with patch.object(MessageDispatcher, '__init__', lambda self, *args: None):
            dispatcher = MessageDispatcher.__new__(MessageDispatcher)
            dispatcher.feishu_api = mock_api
            dispatcher.bot_key = "test"

            callback = dispatcher._make_stream_card_callback("chat_id_123", "test message")
            # 应该能接受三个参数而不抛 TypeError
            async def test_call():
                await callback("thinking...", False, ["mcp__MiniMax__web_search"])
            asyncio.get_event_loop().run_until_complete(test_call())


if __name__ == '__main__':
    unittest.main()
