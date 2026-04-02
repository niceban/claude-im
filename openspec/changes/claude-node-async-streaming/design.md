## Context

当前架构（三层）：
```
OpenClaw Gateway → bridge → claude_node → Claude CLI
```

### 当前问题

| 问题 | 位置 | 说明 |
|------|------|------|
| Stub代码 | server.py:97-118 | chat_completions返回占位符 |
| Stub代码 | adapter.py:57-68 | send()返回假数据 |
| Session泄漏 | manager.py:77 | backend.destroy_session不杀subprocess |
| 无async | adapter.py | 未使用send_nowait()模式 |
| API Key不安全 | settings.py:5 | 默认值无校验 |

### 目标架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    openclaw-claude-bridge                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   OpenClaw Gateway                                               │
│        │                                                        │
│        │ HTTP (OpenAI-compatible)                               │
│        ▼                                                        │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Starlette HTTP Server                                   │   │
│   │  ├── POST /v1/chat/completions (stream=true/false)   │   │
│   │  ├── GET /health                                        │   │
│   │  └── GET /v1/models                                     │   │
│   └────────────────────┬────────────────────────────────────┘   │
│                        │                                         │
│   ┌────────────────────▼────────────────────────────────────┐   │
│   │  AdapterProcessManager                                     │   │
│   │  ├── get_controller(session_id)                         │   │
│   │  ├── send_message(prompt, session_id, stream)          │   │
│   │  └── destroy_session(session_id)                        │   │
│   └────────────────────┬────────────────────────────────────┘   │
│                        │                                         │
│   ┌────────────────────▼────────────────────────────────────┐   │
│   │  ClaudeControllerProcess (mode: direct|tmux)              │   │
│   │                                                         │   │
│   │  mode: "direct" (默认)                               │   │
│   │      ├── subprocess.Popen                             │   │
│   │      ├── controller.send_nowait()  ← 异步           │   │
│   │      └── controller.wait_for_result()                 │   │
│   │                                                         │   │
│   │  mode: "tmux" (1%场景)                               │   │
│   │      ├── tmux send-keys (注入命令)                   │   │
│   │      ├── tmux capture-pane (捕获输出)                 │   │
│   │      └── tmux kill-session (清理)                     │   │
│   └────────────────────┬────────────────────────────────────┘   │
│                        │                                         │
│                        ▼                                         │
│              claude_node (Python)                               │
│                        │                                         │
│                        ▼                                         │
│              Claude Code CLI                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Goals / Non-Goals

**Goals:**
- 替换Stub代码，实现真实调用链
- 实现async streaming（SSE流式推送）
- 打通Session lifecycle与subprocess lifecycle
- 遵循TDD：每个模块独立测试通过后再进入下一模块
- Canary策略渐进部署

**Non-Goals:**
- 不修改OpenClaw Core
- 不废弃cliBackends（保留作为fallback）
- tmux不是主路径（99% direct，1% tmux注入）

## Decisions

### Decision 1: HTTP框架选择Starlette

**选择**：Starlette（同步模式）

**理由**：
- 轻量级，比FastAPI少依赖
- async streaming在adapter层实现，不依赖HTTP框架async
- uvicorn支持热重载

**替代方案**：
- FastAPI：更重，有自动OpenAPI文档
- 结论：Starlette更轻量，足够

### Decision 2: Session管理策略

**选择**：内存Map + LRU驱逐 + subprocess清理联动 + zombie reaping

**理由**：
- 最小实现复杂度
- destroy_session()必须同时清理backend状态AND杀subprocess
- 服务重启session丢失是可接受的风险
- zombie reaping防止孤儿进程累积

**实现**：
```python
# manager.py
def destroy_session(self, session_id):
    # 1. 清理backend
    self._backend.destroy_session(session_id)
    # 2. 清理subprocess（关键！）
    adapter = get_process_manager()
    adapter.destroy_session(session_id)

# zombie reaping机制
def _reap_zombies(self):
    """定期检测和清理zombie subprocess"""
    for pid in self._active_pids:
        if not self._is_process_alive(pid):
            self._cleanup_dead_process(pid)
```

**替代方案**：
- Redis持久化：更稳定但增加运维复杂度
- 结论：内存Map足够，subprocess清理是重点

### Decision 2.1: Zombie Reaping机制

**问题**：subprocess可能因为SIGTERM未送达或crash而变成zombie

**实现**：后台线程定期检测
```python
class AdapterProcessManager:
    def __init__(self):
        self._zombie_check_interval = 60  # 每60秒检测
        self._active_pids: set[int] = set()

    def _start_zombie_reaper(self):
        """启动zombie检测线程"""
        def check_loop():
            while True:
                time.sleep(self._zombie_check_interval)
                self._reap_zombies()

        thread = threading.Thread(target=check_loop, daemon=True)
        thread.start()

    def _reap_zombies(self):
        """检测并清理zombie subprocess"""
        for pid in list(self._active_pids):
            if not self._is_process_alive(pid):
                self._cleanup_dead_process(pid)
                self._active_pids.discard(pid)
```

### Decision 3: Bridge不做Session池化

**选择**：Session生命周期由claude_node内部管理

**理由**：
- claude_node已有成熟的session管理（fork/resume）
- Bridge只做协议转换，不做业务逻辑
- 保持Bridge薄而简单

### Decision 4: async流式实现

**选择**：使用send_nowait() + wait_for_result()异步模式 + SSE推送

**理由**：
- send()是同步阻塞，不利于流式
- send_nowait()立即返回，不阻塞
- wait_for_result()可以配合SSE实现流式
- on_message callback支持实时token推送

**实现模式**：
```python
# adapter.py
def send_async(self, prompt, session_id, on_message):
    controller = self.get_controller(session_id)
    controller.send_nowait(prompt)  # 非阻塞

def wait_for_result_async(self, timeout):
    result = controller.wait_for_result(timeout=timeout)  # 等待结果
    return result
```

**替代方案**：
- 直接用send()：阻塞直到完成，无法流式
- 结论：send_nowait()是实现流式的唯一路径

### Decision 5: tmux作为交互注入通道

**选择**：tmux session管理，但不作为主通信路径

**架构**：
```
正常流程（99%）：
client → HTTP → bridge → claude_node → Claude CLI
                              (stdin/stdout)

特殊交互（1%）：
检测到异常pattern → tmux send-keys "y" → 注入确认
                → tmux send-keys "Ctrl-C" → 中断
```

**tmux接口**：
```python
class TmuxManager:
    def create_session(session_id) -> None
    def send_keys(session_id, keys) -> None
    def capture_pane(session_id) -> str
    def kill_session(session_id) -> None
    def detect_pattern(pattern) -> bool  # 检测异常
```

**使用场景**：
- "Do you want to proceed?" → send-keys "y"
- "Enter your choice:" → send-keys "2"
- 超时/卡住 → send-keys "Ctrl-C" 重试

### Decision 5.1: tmux Session生命周期绑定

**问题**：tmux session独立管理，与ClaudeControllerProcess生命周期无绑定

**解决**：tmux session与ClaudeControllerProcess同生命周期
```python
class ClaudeControllerProcess:
    def __init__(self, session_id: str, mode: str = "direct"):
        self.session_id = session_id
        self.mode = mode
        if mode == "tmux":
            self._tmux = TmuxManager()
            self._tmux.create_session(session_id)
        else:
            self._tmux = None

    def __del__(self):
        """生命周期结束时清理tmux"""
        if self._tmux and self.mode == "tmux":
            self._tmux.kill_session(self.session_id)
```

### Decision 5.2: tmux并发限制

**问题**：50并发 = 50 tmux session，可能耗尽资源

**解决**：会话数量限制 + LRU驱逐
```python
class TmuxManager:
    MAX_SESSIONS = 10  # 最大tmux session数
    SESSION_TIMEOUT = 300  # 5分钟无活动超时

    def acquire_session(self, session_id: str) -> bool:
        """获取tmux session，超限则驱逐最老的"""
        if len(self._active_sessions) >= self.MAX_SESSIONS:
            self._evict_lru_session()
        return self.create_session(session_id)
```

### Decision 6: Canary流量切换策略

**选择**：渐进式canary切换（1% → 10% → 50% → 100%）

| 阶段 | 流量比例 | 验证目标 |
|------|----------|----------|
| Phase 1 | 1% | 基础功能验证 |
| Phase 2 | 10% | 错误率和延迟对比 |
| Phase 3 | 50% | 长时间稳定性 |
| Phase 4 | 100% | 全量切换 |

### Decision 7: API Key认证方案

**选择**：X-API-Key header认证 + 启动校验

**实现**：
```python
# settings.py
API_KEY = os.getenv("BRIDGE_API_KEY")
if not API_KEY or API_KEY == "change-me-in-production":
    raise ValueError("BRIDGE_API_KEY must be set to a secure value")
```

**理由**：
- 与OpenAI API兼容
- 启动时检测默认值，拒绝启动
- 必需配置，不能有默认值

### Decision 8: 超时处理机制

**选择**：分层超时

| 层级 | 超时时间 | 处理 |
|------|----------|------|
| claude_node send | 120s | 返回超时错误 |
| Session idle | 1800s (30min) | LRU驱逐 |
| Cleanup interval | 60s | 后台线程 |

**超时返回格式**（OpenAI标准）：
```json
{
  "error": {
    "message": "Request timeout after 120s",
    "type": "internal_error",
    "code": "timeout",
    "param": null,
    "status": 504
  }
}
```

## TDD模块顺序

遵循：每个模块独立测试通过后再进入下一模块

```
Phase 1:
┌─────────────────┐
│ 1. stub-api     │ ← 先写测试，替换server.py Stub
└───────┬─────────┘
        │ 测试通过
        ▼
┌─────────────────┐
│ 2. stub-adapter │ ← 先写测试，替换adapter.send() Stub
└───────┬─────────┘
        │ 测试通过
        ▼
┌─────────────────┐
│ 3. lifecycle    │ ← 先写测试，打通Session和subprocess
└───────┬─────────┘
        │ 测试通过
        ▼
┌─────────────────┐
│ 4. config       │ ← 先生成OpenClaw配置
└─────────────────┘

Phase 2:
┌─────────────────┐
│ 5. async-stream │ ← 先写测试，实现async streaming
└─────────────────┘

Phase 3:
┌─────────────────┐
│ 6. tmux         │ ← 先写测试，实现tmux接口
└─────────────────┘

Phase 4:
┌─────────────────┐
│ 7. integration  │ ← 端到端测试
└─────────────────┘
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| claude_node Alpha状态 | 固定版本，避免升级 |
| Session重启丢失 | 可接受的短期限制 |
| tmux性能开销 | 默认关闭，仅1%场景使用 |
| async模式复杂度 | TDD确保每个阶段正确 |

## Open Questions

1. ~~tmux session数量上限？（50并发=50 tmux session）~~ → **已解决**：限制MAX_SESSIONS=10 + LRU驱逐
2. send_nowait()超时后的重试机制？→ **待定**：建议3次重试 + exponential backoff
3. ~~on_message callback的SSE推送格式？~~ → **已解决**：使用OpenAI标准格式（见async-stream spec）
