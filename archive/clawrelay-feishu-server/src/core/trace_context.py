"""
Trace Context 模块

每个请求分配一个 UUID，作为 trace_id 贯穿全链路日志。
"""

import uuid
import contextvars
from typing import Optional

# ─── Context Variable ────────────────────────────────────────────────────────

_current_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_trace_id", default=None
)


def generate_trace_id() -> str:
    """生成一个新的 trace_id"""
    return str(uuid.uuid4())


def set_trace_id(trace_id: str) -> contextvars.Token:
    """设置当前上下文的 trace_id"""
    return _current_trace_id.set(trace_id)


def get_trace_id() -> Optional[str]:
    """获取当前上下文的 trace_id"""
    return _current_trace_id.get()


def reset_trace_id(token: contextvars.Token):
    """恢复之前的 trace_id"""
    _current_trace_id.reset(token)


class TraceContext:
    """上下文管理器，自动生成和设置 trace_id"""

    __slots__ = ("token", "trace_id")

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or generate_trace_id()
        self.token: Optional[contextvars.Token] = None

    def __enter__(self):
        self.token = set_trace_id(self.trace_id)
        return self.trace_id

    def __exit__(self, *args):
        if self.token is not None:
            reset_trace_id(self.token)
