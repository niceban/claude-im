"""
Prometheus 指标模块

暴露标准 /metrics 端点，供 Prometheus 抓取。
"""

import asyncio
import logging
import threading
import time
from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)

# ─── Counters ───────────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "claude_im_requests_total",
    "总请求数",
    ["bot_key", "status"],  # status: success | error | timeout
)

ERROR_COUNT = Counter(
    "claude_im_errors_total",
    "错误总数",
    ["bot_key", "error_type"],  # error_type: 401 | 403 | 429 | 500 | 502 | 503 | other
)

MCP_FALLBACK_COUNT = Counter(
    "claude_im_mcp_fallback_total",
    "MCP 降级次数",
    ["bot_key"],
)

INPUT_TOKENS = Counter(
    "claude_im_input_tokens_total",
    "输入 token 总数",
    ["bot_key", "model"],
)

OUTPUT_TOKENS = Counter(
    "claude_im_output_tokens_total",
    "输出 token 总数",
    ["bot_key", "model"],
)

CACHE_TOKENS = Counter(
    "claude_im_cache_tokens_total",
    "Cache token 总数",
    ["bot_key", "model"],
)

# ─── Gauges ────────────────────────────────────────────────────────────────

ACTIVE_SESSIONS = Gauge(
    "claude_im_active_sessions",
    "当前活跃会话数",
    ["bot_key"],
)

CONTROLLER_POOL_SIZE = Gauge(
    "claude_im_controller_pool_size",
    "ClaudeController 连接池当前大小",
    [],
)

MEMORY_USAGE_BYTES = Gauge(
    "claude_im_memory_bytes",
    "进程内存使用（字节）",
    [],
)

# ─── Histograms ────────────────────────────────────────────────────────────

REQUEST_LATENCY_MS = Histogram(
    "claude_im_request_latency_ms",
    "请求延迟分布（毫秒）",
    ["bot_key"],
    buckets=(100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000, 120000),
)


# ─── MetricsCollector ────────────────────────────────────────────────────────

class MetricsCollector:
    """定期采集系统级指标（内存、活跃会话数）"""

    def __init__(self, poll_interval: float = 15.0):
        self._poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()

    def start(self, loop: asyncio.AbstractEventLoop):
        if self._running:
            return
        self._running = True
        self._task = loop.create_task(self._poll())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll(self):
        import psutil
        process = psutil.Process()

        while self._running:
            try:
                # 内存
                mem_info = process.memory_info()
                MEMORY_USAGE_BYTES.set(mem_info.rss)

                # Controller pool size（全局）
                from src.adapters.claude_node_adapter import MAX_POOL_SIZE, ClaudeNodeAdapter
                # pool size 通过 Prometheus gauge 更新的方式已在 adapter 中处理

            except Exception as e:
                logger.warning("[Metrics] 采集失败: %s", e)

            await asyncio.sleep(self._poll_interval)

    @staticmethod
    def metrics() -> tuple[bytes, str]:
        """返回 Prometheus metrics 文本格式"""
        return generate_latest(), CONTENT_TYPE_LATEST


def record_request(
    bot_key: str,
    status: str,
    latency_ms: int,
    error_type: Optional[str] = None,
    is_mcp_fallback: bool = False,
):
    """记录一次请求的指标"""
    REQUEST_COUNT.labels(bot_key=bot_key, status=status).inc()
    REQUEST_LATENCY_MS.labels(bot_key=bot_key).observe(latency_ms)
    if error_type:
        ERROR_COUNT.labels(bot_key=bot_key, error_type=error_type).inc()
    if is_mcp_fallback:
        MCP_FALLBACK_COUNT.labels(bot_key=bot_key).inc()


def record_active_sessions(bot_key: str, count: int):
    ACTIVE_SESSIONS.labels(bot_key=bot_key).set(count)


def record_tokens(bot_key: str, model: str, input_tokens: int, output_tokens: int, cache_tokens: int = 0):
    """记录 token 消耗"""
    if input_tokens > 0:
        INPUT_TOKENS.labels(bot_key=bot_key, model=model).inc(input_tokens)
    if output_tokens > 0:
        OUTPUT_TOKENS.labels(bot_key=bot_key, model=model).inc(output_tokens)
    if cache_tokens > 0:
        CACHE_TOKENS.labels(bot_key=bot_key, model=model).inc(cache_tokens)


_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
