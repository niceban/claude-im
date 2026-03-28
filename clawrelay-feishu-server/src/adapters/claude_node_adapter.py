"""
ClaudeNode 适配器模块

直接 import claude-node，驱动 Claude Code CLI 子进程。
与飞书 IM 层完整打通：per-session 隔离、async 流式、subprocess 健康管理。
"""

import asyncio
import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional, Union

from claude_node import ClaudeController, ClaudeMessage

logger = logging.getLogger(__name__)


# ─── Stream Events ───────────────────────────────────────────────────────────

@dataclass
class TextDelta:
    text: str


@dataclass
class ThinkingDelta:
    text: str


@dataclass
class ToolUseStart:
    name: str


@dataclass
class AskUserQuestionEvent:
    tool_call_id: str
    questions: list


StreamEvent = Union[TextDelta, ThinkingDelta, ToolUseStart, AskUserQuestionEvent]


# ─── ClaudeNode Adapter ───────────────────────────────────────────────────────

MAX_POOL_SIZE = 10  # 最多缓存多少个 session 的 controller


class ClaudeNodeAdapter:
    """
    直接 import claude-node 的适配器。

    关键设计（per-session 隔离版）：
    - 每个 session 独立的 ClaudeController（controller pool）
    - 每个 controller 有自己的 _send_lock，不同 session 完全并行
    - per-session asyncio.Lock（同一 session 的并发保护）
    - subprocess 死亡检测：流式过程中心跳检测，死了立即重启
    - 流式事件用 asyncio.Queue 跨线程传递，不阻塞 event loop
    """

    def __init__(
        self,
        model: str,
        working_dir: str,
        env_vars: Optional[Dict[str, str]] = None,
        system_prompt: str = "",
    ):
        self.model = model
        self.working_dir = working_dir
        self.env_vars = env_vars or {}
        self.system_prompt = system_prompt

        # per-session controller pool: session_key → ClaudeController
        self._controllers: Dict[str, ClaudeController] = {}
        self._controller_locks: Dict[str, threading.RLock] = {}  # per-controller lock
        self._controller_last_used: Dict[str, float] = {}  # LRU 追踪
        self._pool_lock = threading.Lock()  # 管理 pool 本身的锁

        # per-session asyncio.Lock（不同 session 不互等）
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._session_locks_lock = asyncio.Lock()

        logger.info(
            f"[ClaudeNode] 初始化: model={self.model}, "
            f"working_dir={self.working_dir}, env_vars_count={len(self.env_vars)}"
        )

    async def _get_session_lock(self, session_key: str) -> asyncio.Lock:
        """获取或创建 per-session lock"""
        async with self._session_locks_lock:
            if session_key not in self._session_locks:
                self._session_locks[session_key] = asyncio.Lock()
            return self._session_locks[session_key]

    def _evict_lru_if_needed(self):
        """如果 pool 满了，驱逐最久未使用的 session controller"""
        if len(self._controllers) < MAX_POOL_SIZE:
            return
        oldest_key = min(self._controller_last_used, key=self._controller_last_used.get)
        logger.info(f"[ClaudeNode] Controller pool 满，驱逐 LRU session: {oldest_key}")
        ctrl = self._controllers.pop(oldest_key, None)
        if ctrl:
            try:
                ctrl.stop()
            except Exception:
                pass
        self._controller_locks.pop(oldest_key, None)
        self._controller_last_used.pop(oldest_key, None)

    def _ensure_controller_alive(self, session_key: str) -> bool:
        """检查指定 session 的 subprocess 是否活着"""
        ctrl = self._controllers.get(session_key)
        if ctrl is None:
            return False
        if not ctrl.alive:
            logger.warning(f"[ClaudeNode] session={session_key} 子进程已死亡，标记待重建")
            try:
                ctrl.stop()
            except Exception:
                pass
            del self._controllers[session_key]
            self._controller_locks.pop(session_key, None)
            self._controller_last_used.pop(session_key, None)
            return False
        return True

    def _get_controller(self, session_key: str, system_prompt: str = "") -> ClaudeController:
        """获取或创建 per-session ClaudeController（线程安全）"""
        # 快速路径：session 已存在
        if session_key in self._controllers:
            self._controller_last_used[session_key] = time.time()
            return self._controllers[session_key]

        # 创建新的 controller
        with self._pool_lock:
            # 驱逐 LRU 如果 pool 满了
            self._evict_lru_if_needed()

            # Double-check：另一个线程可能已经创建了
            if session_key in self._controllers:
                return self._controllers[session_key]

            # 将 env_vars 注入 os.environ，让 subprocess 能访问认证 token
            # claude-node 的 Popen 使用 {**os.environ}，必须在此之前注入
            env_snapshot = {k: os.environ.get(k) for k in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")}
            try:
                for k, v in (self.env_vars or {}).items():
                    os.environ[k] = v

                ctrl = ClaudeController(
                    system_prompt=system_prompt or self.system_prompt,
                    skip_permissions=True,
                    model=self.model,
                    cwd=self.working_dir or None,
                )
                # 非阻塞启动（不等待 init），init 由后台线程完成
                started = ctrl.start(wait_init_timeout=0)
                self._controllers[session_key] = ctrl
                self._controller_locks[session_key] = threading.RLock()
                self._controller_last_used[session_key] = time.time()

                if started:
                    def wait_init():
                        ok = ctrl._wait_for_init(30)
                        if ok:
                            logger.info(f"[ClaudeNode] session={session_key} 初始化完成（后台）")
                        else:
                            logger.warning(f"[ClaudeNode] session={session_key} 初始化超时（30s）")
                    threading.Thread(target=wait_init, daemon=True).start()

                logger.info(f"[ClaudeNode] session={session_key} 子进程已启动 (pool_size={len(self._controllers)})")
            finally:
                # 恢复 os.environ，不污染全局状态
                for k, v in env_snapshot.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

            return ctrl

    async def stream_chat(
        self,
        messages: List[dict],
        system_prompt: str = "",
        session_id: str = "",
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        核心接口：per-session 流式聊天。

        流程：
        1. 获取 per-session asyncio.Lock（不同 session 不互等，最多等 30s）
        2. 检查 subprocess 状态，死了立即重建
        3. 在线程池运行 send()，用 asyncio.Queue 收集 on_message 事件
        4. 异步消费事件，yield 流式事件
        5. 心跳检测：每秒检查一次 subprocess 健康状态
        """
        if not messages:
            return

        session_key = session_id or "_default"
        session_lock = await self._get_session_lock(session_key)

        # 等待该 session 的锁（最多等 30s）
        try:
            await asyncio.wait_for(session_lock.acquire(), timeout=3600.0)
        except asyncio.TimeoutError:
            logger.warning(f"[ClaudeNode] session {session_key} 等待锁超时")
            yield TextDelta(text="[系统] 当前有消息正在处理，请稍后重试。")
            return

        try:
            # 确保 subprocess 活着（per-session controller）
            if not self._ensure_controller_alive(session_key):
                ctrl = self._get_controller(session_key, system_prompt)
                if not ctrl.alive:
                    yield TextDelta(text="[系统] Claude 服务启动失败，请稍后重试。")
                    return

            # 提取当前消息文本
            current_message = messages[-1].get("content", "") if messages else ""
            if isinstance(current_message, list):
                text_parts = []
                for block in current_message:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "image_url":
                            text_parts.append(f"[Image: {block.get('url', '')}]")
                current_message = "\n".join(text_parts)

            # asyncio.Queue：跨线程传递 on_message 事件
            evt_queue: asyncio.Queue[ClaudeMessage] = asyncio.Queue()
            # result_queue：传递 send() 最终结果（线程安全）
            result_queue: queue.Queue[tuple] = queue.Queue()

            def on_message(msg: ClaudeMessage):
                # 在后台线程执行，抛到 asyncio event loop
                evt_queue.put_nowait(msg)

            def run_send():
                t0 = time.time()
                try:
                    ctrl = self._get_controller(session_key, system_prompt)
                    ctrl.on_message = on_message
                    result = ctrl.send(current_message, timeout=3600)
                    result_queue.put(("done", result))
                except Exception as e:
                    # 不再有 ClaudeSendConflictError（每个 session 独立 controller）
                    # 但保留防御性处理
                    logger.error(f"[ClaudeNode] send 异常: {e}, t={time.time()-t0:.3f}s")
                    result_queue.put(("error", e))
                finally:
                    result_queue.put(("stop", None))

            # 在线程池运行 send()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_send)

            # 异步消费事件
            tool_names_seen: set = set()
            text_accumulated = False
            send_finished = False

            while True:
                try:
                    # 非阻塞检查 send 结果
                    try:
                        tag, data = result_queue.get_nowait()
                    except queue.Empty:
                        tag, data = None, None

                    if tag == "error":
                        yield TextDelta(text=f"[系统] 处理出错：{data}")
                        return
                    elif tag == "done":
                        send_finished = True
                        result = data
                        if result is None:
                            # send() 超时（300s）或异常返回 None
                            if not text_accumulated:
                                yield TextDelta(text="[系统] AI 处理超时（1小时），请稍后重试或尝试更具体的问题。")
                        elif not text_accumulated:
                            fallback = (
                                getattr(result, 'result_text', '')
                                or (result.raw.get('result', '') if result.raw else '')
                            )
                            if fallback:
                                yield TextDelta(text=fallback)
                        break

                    # 等待 on_message 事件（最多等 1.5s，充当心跳检测）
                    try:
                        msg: ClaudeMessage = await asyncio.wait_for(
                            evt_queue.get(), timeout=1.5
                        )
                    except asyncio.TimeoutError:
                        # 心跳：检查 subprocess 是否还活着
                        if not self._ensure_controller_alive(session_key):
                            logger.warning("[ClaudeNode] 流式中子进程死亡，尝试重建")
                            yield TextDelta(text="[系统] 连接中断，正在恢复...")
                            return
                        continue

                    # 解析 ClaudeMessage 事件
                    if msg.is_assistant:
                        for text in (msg.assistant_texts or []):
                            if text:
                                text_accumulated = True
                                yield TextDelta(text=text)

                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            name = tc.get("name", "")
                            if name == "AskUserQuestion":
                                try:
                                    args = json.loads(tc.get("arguments", "{}"))
                                    yield AskUserQuestionEvent(
                                        tool_call_id=tc.get("id", ""),
                                        questions=args.get("questions", []),
                                    )
                                except json.JSONDecodeError:
                                    pass
                            elif name and name not in tool_names_seen:
                                tool_names_seen.add(name)
                                yield ToolUseStart(name=name)

                except asyncio.CancelledError:
                    logger.info(f"[ClaudeNode] session {session_key} 流式被取消")
                    return

        finally:
            session_lock.release()

    async def check_health(self) -> bool:
        """健康检查（检查所有 session 的 controller）"""
        try:
            for key, ctrl in list(self._controllers.items()):
                if not ctrl.alive:
                    logger.warning(f"[ClaudeNode] session={key} 子进程已死亡")
                    return False
            return len(self._controllers) > 0
        except Exception as e:
            logger.warning(f"[ClaudeNode] 健康检查失败: {e}")
            return False

    def prewarm(self):
        """预热一个 default session controller（启动时调用，避免首次消息 30s 冷启动）"""
        default_key = "_default"
        if default_key not in self._controllers:
            with self._pool_lock:
                if default_key not in self._controllers:
                    logger.info("[ClaudeNode] 预热 default session controller...")
                    ctrl = ClaudeController(
                        system_prompt=self.system_prompt,
                        skip_permissions=True,
                        model=self.model,
                        cwd=self.working_dir or None,
                    )
                    ctrl.start(wait_init_timeout=30)
                    self._controllers[default_key] = ctrl
                    self._controller_locks[default_key] = threading.RLock()
                    self._controller_last_used[default_key] = time.time()
                    logger.info("[ClaudeNode] 预热完成")

    def stop(self):
        """停止所有 controller（清理资源）"""
        for key, ctrl in list(self._controllers.items()):
            try:
                ctrl.stop()
            except Exception as e:
                logger.warning(f"[ClaudeNode] 停止 session={key} 异常: {e}")
        self._controllers.clear()
        self._controller_locks.clear()
        self._controller_last_used.clear()
        logger.info("[ClaudeNode] 所有 controller 已停止")
