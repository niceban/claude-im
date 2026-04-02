# tdd-test-suite 模块规格

## 概述

tdd-test-suite模块定义测试规范和测试基础设施。

## TDD流程

```
┌─────────────────────────────────────────────────────────────┐
│                    TDD开发流程                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  RED   →  写测试，测试应该FAIL                            │
│           ↓                                                  │
│  GREEN →  写最小实现，让测试PASS                           │
│           ↓                                                  │
│  REFACTOR → 重构代码，保持测试PASS                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 测试基础设施

### 测试文件结构

```
openclaw-claude-bridge/
├── tests/
│   ├── conftest.py              # pytest配置和fixtures
│   ├── test_stub_api.py         # 模块1测试
│   ├── test_stub_adapter.py      # 模块2测试
│   ├── test_lifecycle.py         # 模块3测试
│   ├── test_async_stream.py      # 模块5测试
│   ├── test_tmux.py             # 模块6测试
│   ├── test_integration.py       # 集成测试
│   └── test_e2e.py              # E2E测试
```

### conftest.py

```python
import os
import sys

# 设置测试环境
os.environ["BRIDGE_API_KEY"] = "test-key"
os.environ["CLAUDE_NODE_PATH"] = "/private/tmp/claude-node"
os.environ["TMUX_ENABLED"] = "false"  # 测试时关闭tmux

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

@pytest.fixture
def mock_claude_controller():
    """Mock ClaudeController for unit tests"""
    from unittest.mock import MagicMock
    controller = MagicMock()
    controller.send_nowait = MagicMock()
    controller.wait_for_result = MagicMock(return_value=MagicMock(text="test response"))
    controller.start = MagicMock()
    controller.stop = MagicMock()
    controller.alive = True
    return controller

@pytest.fixture
def session_manager():
    """Create session manager for tests"""
    from session_mapping.manager import SessionMappingManager
    from session_mapping.backend import InMemorySessionBackend
    return SessionMappingManager(backend=InMemorySessionBackend())

@pytest.fixture
def adapter():
    """Create adapter for tests"""
    from claude_node_adapter.adapter import AdapterProcessManager
    return AdapterProcessManager()
```

## 测试命名规范

```python
# 格式: test_{module}_{scenario}_{expected_behavior}

def test_stub_api_chat_completions_returns_real_response():
    """验证chat_completions返回真实响应而非占位符"""
    pass

def test_stub_adapter_send_calls_controller_send_nowait():
    """验证send调用controller.send_nowait"""
    pass

def test_lifecycle_destroy_session_kills_subprocess():
    """验证destroy_session同时杀subprocess"""
    pass

def test_async_stream_sse_format_correct():
    """验证SSE格式正确"""
    pass
```

## Mock策略

| 模块 | Mock对象 | 说明 |
|------|----------|------|
| stub-api | adapter.send_message | 不真正调用adapter |
| stub-adapter | ClaudeController | 不真正调用claude_node |
| lifecycle | adapter.destroy_session | 不真正杀进程 |
| async-stream | on_message callback | 不真正SSE推送 |
| tmux | tmux命令 | 不真正执行tmux |

## 覆盖率要求

| 模块 | 最低覆盖率 |
|------|-----------|
| stub-api | 80% |
| stub-adapter | 80% |
| lifecycle | 80% |
| async-stream | 70% |
| tmux | 70% |
| integration | 60% |

## 集成测试要求

集成测试使用真实claude_node：

```python
@pytest.mark.integration
def test_real_claude_node_call():
    """真实调用claude_node"""
    # 需要 CLAUDE_NODE_PATH 环境变量
    # 需要真实claude_node可执行
    pass
```

## 验收标准

- [ ] 所有测试文件遵循TDD命名规范
- [ ] conftest.py提供必要的fixtures
- [ ] Mock策略明确
- [ ] 覆盖率达标
- [ ] 集成测试标记@pytest.mark.integration
