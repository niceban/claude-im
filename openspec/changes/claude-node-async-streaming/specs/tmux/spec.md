# tmux 模块规格

## 概述

tmux模块提供交互注入通道。用于1%场景下的特殊交互（弹窗确认、Ctrl-C中断等）。

**重要**：tmux不是主路径，99%走direct模式，tmux仅作为"后门"使用。

## 架构

```
正常流程（99%）：
client → HTTP → bridge → claude_node → Claude CLI
                              (direct stdin/stdout)

特殊交互（1%）：
bridge → tmux capture-pane → 检测异常pattern
bridge → tmux send-keys "y" → 注入确认
bridge → tmux send-keys "Ctrl-C" → 中断
```

## TmuxManager接口

```python
class TmuxManager:
    """tmux session管理器"""

    def create_session(self, session_id: str, cwd: str = "/tmp") -> None:
        """创建tmux session"""
        # tmux new-session -d -s claude-{session_id}
        # tmux send-keys "cd {cwd}" Enter
        pass

    def send_keys(self, session_id: str, keys: str) -> None:
        """发送按键到tmux session"""
        # tmux send-keys -t claude-{session_id} "{keys}"
        pass

    def capture_pane(self, session_id: str) -> str:
        """捕获tmux pane内容"""
        # tmux capture-pane -t claude-{session_id} -p
        pass

    def kill_session(self, session_id: str) -> None:
        """销毁tmux session"""
        # tmux kill-session -t claude-{session_id}
        pass

    def detect_pattern(self, pane_content: str) -> Optional[str]:
        """检测异常pattern，返回匹配内容或None"""
        patterns = [
            "Do you want to proceed\\? \\[Y/n\\]",
            "Enter your choice:",
            "Press Ctrl-C to cancel",
            "Do you confirm\\?",
        ]
        # 返回匹配到的pattern
        pass

    def inject_confirmation(self, session_id: str) -> bool:
        """注入确认（y）"""
        if self.detect_pattern(self.capture_pane(session_id)):
            self.send_keys(session_id, "y")
            return True
        return False

    def inject_interrupt(self, session_id: str) -> bool:
        """注入中断（Ctrl-C）"""
        self.send_keys(session_id, "C-c")
        return True
```

## 使用场景

| 场景 | 检测Pattern | 注入 |
|------|-------------|------|
| 权限确认 | "Do you want to proceed? [Y/n]" | "y" |
| 选择确认 | "Enter your choice:" | "2" |
| 取消操作 | "Press Ctrl-C to cancel" | "Ctrl-C" |
| 超时卡住 | timeout检测 | "Ctrl-C" |

## 配置

```python
# settings.py
TMUX_ENABLED = os.getenv("TMUX_ENABLED", "false")  # 默认关闭
TMUX_MODE = os.getenv("TMUX_MODE", "off")  # "off" | "passive" | "active"
```

## tmux模式

| 模式 | 说明 |
|------|------|
| off | 不使用tmux，direct模式 |
| passive | 创建tmux观测窗口，但不主动注入 |
| active | 检测到异常时自动注入 |

## 并发限制

| 配置 | 默认值 | 说明 |
|------|--------|------|
| MAX_SESSIONS | 10 | 最大tmux session数 |
| SESSION_TIMEOUT | 300 | 5分钟无活动超时 |

**说明**：当达到MAX_SESSIONS时，驱逐最老的session

## Crash Recovery

tmux session可能因进程crash而处于僵死状态。TmuxManager需要检测并清理：

```python
def _check_session_health(self, session_id: str) -> bool:
    """检测session是否健康"""
    try:
        # 尝试capture pane，如果session已僵死会失败
        self.capture_pane(session_id)
        return True
    except TmuxError:
        return False

def _recover_session(self, session_id: str) -> None:
    """恢复或重建session"""
    try:
        self.kill_session(session_id)  # 清理僵死session
    except TmuxError:
        pass  # session已不存在
    self.create_session(session_id)  # 重建
```

## 异常Pattern检测

```python
# 示例：检测到"Do you want to proceed?"
pane = tmux.capture_pane("session-xxx")
if "Do you want to proceed" in pane:
    tmux.send_keys("session-xxx", "y")  # 自动确认
```

## 测试要求

1. **测试6.1.1**: tmux session创建
2. **测试6.1.2**: send_keys注入
3. **测试6.1.3**: capture_pane捕获
4. **测试6.1.4**: kill_session清理

## 验收标准

- [ ] tmux session正确创建和销毁
- [ ] send_keys成功注入命令
- [ ] capture_pane正确捕获输出
- [ ] pattern检测准确
- [ ] 默认关闭，不影响正常流程
- [ ] 所有测试通过
- [ ] 并发限制生效（MAX_SESSIONS）
- [ ] crash recovery正常工作
