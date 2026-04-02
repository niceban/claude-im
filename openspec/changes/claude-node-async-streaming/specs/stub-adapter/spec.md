# stub-adapter 模块规格

## 概述

stub-adapter模块负责与claude_node通信。核心任务是**替换当前Stub代码**，真实调用ClaudeController。

## 当前状态

```python
# adapter.py:57-68 (STUB - 必须替换)
def send(self, prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Send prompt to claude-node (placeholder - needs real implementation)."""
    return {
        "type": "result",
        "result_text": f"Response to: {prompt}",  # ← STUB
        "session_id": session_id or self.session_id
    }
```

## claude_node ClaudeController API

```python
from claude_node.controller import ClaudeController

# 初始化
controller = ClaudeController(
    cwd=cwd,
    model=model,
    resume=session_id,  # resume existing session
    on_message=on_message,  # streaming callback
)

# 启动
controller.start(wait_init_timeout=10.0)

# 异步发送（目标实现）
controller.send_nowait(user_text)
result = controller.wait_for_result(timeout=120)

# 停止
controller.stop()
```

## 目标状态

```python
# adapter.py send() (实现后)
def send(self, prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    if not self._alive:
        self.start()

    self.controller.send_nowait(prompt)  # 非阻塞
    result = self.controller.wait_for_result(timeout=self.timeout)

    if result is None:
        raise TimeoutError(f"Request timeout after {self.timeout}s")

    return {
        "type": "result",
        "text": result.text,
        "session_id": self.session_id,
        "tool_errors": result.tool_errors or []
    }

def send_async(self, prompt: str, on_message_callback):
    """异步发送，不阻塞"""
    if not self._alive:
        self.start()
    self.controller.on_message = on_message_callback
    self.controller.send_nowait(prompt)
```

## 接口规格

### send(prompt, session_id) -> Dict

**参数**:
- prompt: str - 用户输入
- session_id: Optional[str] - 会话ID

**返回**:
```python
{
    "type": "result",
    "text": "Claude response text",
    "session_id": "session-xxx",
    "tool_errors": []  // 可选
}
```

**异常**:
- RuntimeError: Controller not started
- TimeoutError: Request timeout

### send_async(prompt, on_message_callback)

**参数**:
- prompt: str - 用户输入
- on_message_callback: Callable[[ClaudeMessage], None] - 流式回调

## 测试要求

1. **测试2.1.1**: 验证controller.send_nowait()被调用
2. **测试2.1.2**: 验证controller.wait_for_result()被调用
3. **测试2.1.3**: session不存在时创建controller
4. **测试2.1.4**: 超时时抛出TimeoutError

## 验收标准

- [ ] 真实调用controller.send_nowait()和wait_for_result()
- [ ] 非阻塞发送
- [ ] 超时处理
- [ ] 所有测试通过
