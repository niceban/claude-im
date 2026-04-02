## Why

当前openclaw-claude-bridge存在三个严重问题：
1. **Stub代码未替换**：server.py返回"(placeholder)"，adapter.send()返回假数据，核心功能不可用
2. **Session泄漏**：LRU驱逐时不杀subprocess，进程累积
3. **缺乏async streaming**：claude_node支持send_nowait()+wait_for_result()异步模式，未被利用

目标：实现一个真正可用的bridge服务，发挥Claude CLI的最大能力。

## What Changes

### Phase 1: 核心可用（Stub替换）
- 替换server.py Stub，真实调用adapter
- 替换adapter.send() Stub，真实调用controller.send()
- 打通Session lifecycle与subprocess lifecycle
- API Key安全加固

### Phase 2: async流式
- 实现send_nowait() + wait_for_result()异步模式
- SSE流式推送
- 超时处理机制

### Phase 3: tmux交互通道
- tmux session管理（创建/发送/捕获/销毁）
- 异常pattern检测
- 交互注入（Ctrl-C、y确认等）

### 非目标
- 不修改OpenClaw Core
- 不废弃cliBackends（降级为fallback保留）
- tmux不是主路径（99%走direct，1%用tmux注入）

## Capabilities

### Phase 1 - 核心可用
- `stub-replacement`: 替换Stub代码，真实调用链
- `session-lifecycle-fix`: 修复Session泄漏
- `api-key-security`: API Key启动校验

### Phase 2 - async流式
- `async-streaming`: send_nowait() + SSE推送
- `timeout-handling`: 超时处理
- `error-recovery`: 进程崩溃检测和恢复

### Phase 3 - tmux交互
- `tmux-interface`: tmux session管理
- `interactive-injection`: 异常pattern检测和注入

## Impact

- 新增服务：openclaw-claude-bridge（端口18792）
- 配置文件：~/.openclaw/openclaw.json更新
- 遵循TDD：每个模块独立测试通过后再进入下一模块
- Canary策略：1% → 10% → 50% → 100%
