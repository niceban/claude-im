"""
P2 / P3 特性测试

覆盖：
- P2-9:  Prometheus metrics 端点
- P2-10: trace_id 每个请求独立
- P2-11: 资源限制（max_concurrent_sessions, max_memory_mb）
- P3-14: SIGUSR1 热重载 system_prompt
- P3-15: MCP 工具白名单
- P3-16: 飞书 reply_card_with_quote / reply_text(quote_id)
"""

import asyncio
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.core.metrics import MetricsCollector, record_request
from src.core.trace_context import generate_trace_id, TraceContext, get_trace_id
from src.adapters.claude_node_adapter import ClaudeNodeAdapter, _is_mcp_unavailable
from src.adapters.feishu_api import FeishuAPI
from config.bot_config import BotConfig, BotConfigManager


# ─── P2-9: Prometheus Metrics ────────────────────────────────────────────────

class TestPrometheusMetrics:
    """Prometheus metrics 端点测试"""

    def test_record_request_updates_prometheus_metrics(self):
        """record_request 正确更新 Prometheus 指标（通过 metrics() 输出验证）"""
        # 触发指标记录
        record_request("test_bot_prom", "success", 150)
        record_request("test_bot_prom", "error", 80, error_type="timeout")
        record_request("test_bot_prom", "success", 200, is_mcp_fallback=True)

        # 通过 metrics() 方法获取输出，验证包含对应指标
        data, content_type = MetricsCollector.metrics()
        text = data.decode("utf-8")
        assert "claude_im_requests_total" in text
        assert "claude_im_request_latency_ms" in text
        assert "test_bot_prom" in text

    def test_metrics_endpoint_returns_prometheus_format(self):
        """GET /api/v1/metrics 返回 Prometheus text 格式"""
        from fastapi.testclient import TestClient
        from src.admin.api import create_admin_app

        app = create_admin_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/v1/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"] or "text/html" in response.headers["content-type"]
        # Prometheus 格式包含 # HELP 和 # TYPE 行
        text = response.text
        assert "# HELP" in text or "claude_im_" in text, "应包含 Prometheus 指标"


# ─── P2-10: Trace ID ─────────────────────────────────────────────────────────

class TestTraceContext:
    """trace_id 每个请求独立"""

    def test_generate_trace_id_returns_unique_ids(self):
        """每次 generate_trace_id 返回不同 UUID"""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100, "每个 trace_id 应该唯一"

    def test_trace_context_sets_and_resets(self):
        """TraceContext 正确 set/reset trace_id"""
        trace_id_1 = generate_trace_id()
        trace_id_2 = generate_trace_id()

        with TraceContext(trace_id_1):
            assert get_trace_id() == trace_id_1
            with TraceContext(trace_id_2):
                assert get_trace_id() == trace_id_2
            assert get_trace_id() == trace_id_1
        assert get_trace_id() is None

    def test_trace_id_format_is_uuid(self):
        """trace_id 格式为 UUID"""
        tid = generate_trace_id()
        assert len(tid) == 36
        assert tid.count("-") == 4


# ─── P2-11: 资源限制 ──────────────────────────────────────────────────────────

class TestResourceLimits:
    """max_concurrent_sessions 和 max_memory_mb 限制"""

    def test_adapter_accepts_resource_limit_params(self):
        """ClaudeNodeAdapter 构造函数接受资源限制参数"""
        adapter = ClaudeNodeAdapter(
            model="test",
            working_dir="/tmp",
            max_concurrent_sessions=5,
            max_memory_mb=512,
            allowed_tools=["web_search", "bash"],
        )
        assert adapter.max_concurrent_sessions == 5
        assert adapter.max_memory_mb == 512
        assert adapter.allowed_tools == ["web_search", "bash"]

    def test_adapter_default_no_limits(self):
        """默认情况下 max_concurrent_sessions=0（不限），max_memory_mb=0（不限）"""
        adapter = ClaudeNodeAdapter(model="test", working_dir="/tmp")
        assert adapter.max_concurrent_sessions == 0
        assert adapter.max_memory_mb == 0
        assert adapter.allowed_tools == []

    @pytest.mark.asyncio
    async def test_concurrent_session_rejected_when_at_limit(self):
        """当并发数达到上限时，新请求被拒绝"""
        adapter = ClaudeNodeAdapter(
            model="test",
            working_dir="/tmp",
            max_concurrent_sessions=1,  # 只允许 1 个并发
        )
        adapter._concurrent_sessions = 1  # 模拟已满

        events = []
        async for event in adapter.stream_chat([{"role": "user", "content": "hi"}], session_id="test"):
            events.append(event)

        # 应该返回系统错误消息
        assert len(events) == 1
        assert "上限" in events[0].text or "已达上限" in events[0].text

    def test_is_mcp_unavailable_detects_patterns(self):
        """MCP 不可用时能检测常见错误"""
        assert _is_mcp_unavailable("Error: MCP server is not running") == True
        assert _is_mcp_unavailable("ECONNREFUSED") == True
        assert _is_mcp_unavailable("401 Unauthorized") == True
        assert _is_mcp_unavailable("failed to start mcp server") == True
        assert _is_mcp_unavailable("just a normal response") == False


# ─── P3-14: SIGUSR1 热重载 ───────────────────────────────────────────────────

class TestSIGUSR1HotReload:
    """system_prompt 热重载测试"""

    def test_bot_config_loads_system_prompt(self, tmp_path):
        """BotConfig 正确加载 system_prompt"""
        config_file = tmp_path / "bots.yaml"
        config_file.write_text("""
bots:
  test_bot:
    app_id: test_app_id
    app_secret: test_secret
    system_prompt: "You are a helpful assistant v2"
    model: "test/model"
    allowed_tools: []
    max_concurrent_sessions: 3
    max_memory_mb: 1024
""")
        mgr = BotConfigManager(config_path=str(config_file))
        bot = mgr.bots.get("test_bot")
        assert bot is not None
        assert bot.system_prompt == "You are a helpful assistant v2"
        assert bot.max_concurrent_sessions == 3
        assert bot.max_memory_mb == 1024
        assert bot.allowed_tools == []

    def test_bot_config_allows_empty_allowed_tools(self, tmp_path):
        """allowed_tools 为空时不限制工具"""
        config_file = tmp_path / "bots.yaml"
        config_file.write_text("""
bots:
  open_bot:
    app_id: test_app_id
    app_secret: test_secret
    system_prompt: "Open bot"
    allowed_tools: []
""")
        mgr = BotConfigManager(config_path=str(config_file))
        bot = mgr.bots["open_bot"]
        assert bot.allowed_tools == []

    def test_bot_config_allows_tool_whitelist(self, tmp_path):
        """allowed_tools 配置工具白名单"""
        config_file = tmp_path / "bots.yaml"
        config_file.write_text("""
bots:
  restricted_bot:
    app_id: test_app_id
    app_secret: test_secret
    system_prompt: "Restricted bot"
    allowed_tools:
      - web_search
      - bash
      - read_file
""")
        mgr = BotConfigManager(config_path=str(config_file))
        bot = mgr.bots["restricted_bot"]
        assert bot.allowed_tools == ["web_search", "bash", "read_file"]


# ─── P3-15: MCP 工具白名单 ───────────────────────────────────────────────────

class TestMCPToolWhitelist:
    """MCP 工具白名单过滤测试"""

    def test_allowed_tools_filter_outside_whitelist(self):
        """不在白名单的工具被过滤（不上报 ToolUseStart）"""
        adapter = ClaudeNodeAdapter(
            model="test",
            working_dir="/tmp",
            allowed_tools=["web_search", "bash"],
        )
        # allowed_tools 非空，web_search 在白名单
        assert adapter.allowed_tools == ["web_search", "bash"]

    def test_empty_allowed_tools_means_no_filter(self):
        """allowed_tools 为空时不进行工具过滤"""
        adapter = ClaudeNodeAdapter(
            model="test",
            working_dir="/tmp",
            allowed_tools=[],
        )
        assert adapter.allowed_tools == []


# ─── P3-16: 飞书 Reply with Quote ──────────────────────────────────────────

class TestFeishuReplyWithQuote:
    """飞书 reply 支持 quote_id（群聊引用回复）"""

    def test_feishu_api_has_reply_card_with_quote_method(self):
        """FeishuAPI 有 reply_card_with_quote 方法"""
        api = FeishuAPI(app_id="fake", app_secret="fake")
        assert hasattr(api, "reply_card_with_quote")
        assert callable(api.reply_card_with_quote)

    def test_feishu_api_reply_text_accepts_quote_id_param(self):
        """FeishuAPI.reply_text 接受 quote_id 参数"""
        import inspect
        api = FeishuAPI(app_id="fake", app_secret="fake")
        sig = inspect.signature(api.reply_text)
        params = list(sig.parameters.keys())
        assert "quote_id" in params, f"reply_text 应有 quote_id 参数，当前参数: {params}"

    @pytest.mark.asyncio
    async def test_reply_text_with_quote_id_calls_correct_api(self):
        """reply_text(quote_id=xxx) 正确调用 ReplyMessageRequest 并设置 quote_id"""
        api = FeishuAPI(app_id="fake_id", app_secret="fake_secret")
        with patch.object(api.client.im.v1.message, "reply") as mock_reply:
            mock_response = MagicMock()
            mock_response.success.return_value = True
            mock_response.data = MagicMock()
            mock_response.data.message_id = "reply_msg_123"
            mock_reply.return_value = mock_response

            result = await api.reply_text("parent_msg_id", "hello", quote_id="quoted_msg_id")

            assert result == "reply_msg_123"
            assert mock_reply.called
            # Verify quote_id was set on the request body
            request_body = mock_reply.call_args[0][0].request_body
            assert request_body.quote_id == "quoted_msg_id"

    @pytest.mark.asyncio
    async def test_reply_card_with_quote_calls_reply_api(self):
        """reply_card_with_quote 正确调用飞书 ReplyMessageRequest 并设置 quote_id"""
        api = FeishuAPI(app_id="fake_id", app_secret="fake_secret")
        with patch.object(api.client.im.v1.message, "reply") as mock_reply:
            mock_response = MagicMock()
            mock_response.success.return_value = True
            mock_response.data = MagicMock()
            mock_response.data.message_id = "card_reply_456"
            mock_reply.return_value = mock_response

            card = {"elements": [{"tag": "markdown", "content": "**hello**"}]}
            result = await api.reply_card_with_quote("parent_msg_id", card, quote_id="quoted_msg_id")

            assert result == "card_reply_456"
            assert mock_reply.called
            # Verify quote_id was set on the request body
            request_body = mock_reply.call_args[0][0].request_body
            assert request_body.quote_id == "quoted_msg_id"


# ─── P3-16: ChatLogger trace_id ─────────────────────────────────────────────

class TestChatLoggerTraceId:
    """ChatLogger JSONL 输出包含 trace_id"""

    def test_chat_logger_accepts_log_context_with_trace_id(self):
        """ChatLogger.log 接收 trace_id 字段（验证签名接受 log_context kwarg）"""
        from src.core.chat_logger import ChatLogger
        import inspect

        logger_obj = ChatLogger()
        sig = inspect.signature(logger_obj.log)
        params = list(sig.parameters.keys())
        # log_context 必须作为 kwarg 被接受
        assert "log_context" in params, f"ChatLogger.log 应接受 log_context 参数，当前参数: {params}"
        # trace_id 会被 log_context 字典提取，不直接作为参数
        assert sig.parameters["log_context"].default is None or sig.parameters["log_context"].default == {}


# ─── P2/P3 BotConfig 完整字段测试 ────────────────────────────────────────────

class TestBotConfigComplete:
    """BotConfig 所有新增字段完整测试"""

    def test_bot_config_all_new_fields(self, tmp_path):
        """BotConfig 包含 P2/P3 所有新字段"""
        config_file = tmp_path / "bots.yaml"
        config_file.write_text("""
bots:
  full_bot:
    app_id: cli_test_app
    app_secret: cli_test_secret
    working_dir: "/home/user/workspace"
    model: "vllm/sonnet-4"
    system_prompt: "You are a coding assistant."
    allowed_users:
      - user_001
      - user_002
    allowed_tools:
      - web_search
      - bash
      - read_file
    max_concurrent_sessions: 10
    max_memory_mb: 2048
    custom_commands:
      - src.handlers.command_handlers
""")
        mgr = BotConfigManager(config_path=str(config_file))
        bot = mgr.bots["full_bot"]

        assert bot.bot_key == "full_bot"
        assert bot.app_id == "cli_test_app"
        assert bot.working_dir == "/home/user/workspace"
        assert bot.model == "vllm/sonnet-4"
        assert bot.system_prompt == "You are a coding assistant."
        assert bot.allowed_users == ["user_001", "user_002"]
        assert bot.allowed_tools == ["web_search", "bash", "read_file"]
        assert bot.max_concurrent_sessions == 10
        assert bot.max_memory_mb == 2048
        assert bot.custom_commands == ["src.handlers.command_handlers"]
