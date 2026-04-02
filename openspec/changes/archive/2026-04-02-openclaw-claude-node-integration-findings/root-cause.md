# Root Cause Analysis — deep-1775095086

## Project Blockers and Current Issues

**Date**: 2026-04-02
**Run ID**: deep-1775095086

---

## Executive Summary

当前项目使用 **cliBackends 作为主执行通道**，而不是 Provider 通道。这与"OpenClaw 做生态壳 + claude-node 做内核"的理想架构有偏差。

---

## Key Findings

### 1. 路由解析结果

**当前 model ref**: `claude-node-cli/MiniMax-M2.7`

**解析路径**: `cliBackends.claude-node-cli` → wrapper.py → claude_node → Claude CLI

**Source**: OpenClaw 解析 cliBackends 时，provider 前缀匹配 `agents.defaults.cliBackends` 中的 key

### 2. Provider 18793 已废弃

| 配置 | 状态 |
|------|------|
| `models.providers.claude-node-cli` (指向 18793) | **已废弃** - clawrelay_bridge 已删除 |
| `cliBackends.claude-node-cli` (wrapper.py) | **生产主路径** |

### 3. Fallback 机制

当 cliBackends 失败时 → 走 `minimax-cn/MiniMax-M2.7` → MiniMax API HTTP

### 4. 架构偏差

**当前架构**:
```
Feishu → OpenClaw Gateway → cliBackends → wrapper.py → claude_node → Claude CLI
```

**理想架构**:
```
Feishu → OpenClaw Gateway → models.providers (HTTP) → bridge → claude_node → Claude CLI
```

**偏差**: 当前用 cliBackends (fallback 通道) 作为主执行路径，而不是用 models.providers (标准 HTTP provider 通道)

---

## Critical Issues

### Issue 1: cliBackends 是 text-only fallback
- **官方定义**: CLI backends 是 "text-only fallback runs" / "safety-net rather than a primary path"
- **能力限制**: tools disabled, no streaming, no OpenClaw tools integration
- **影响**: 无法发挥 Claude CLI 完整能力（tools, skills, streaming events）

### Issue 2: wrapper.py 三合一
wrapper.py 同时承担:
1. OpenClaw 协议适配 (cliBackends 接口)
2. Claude runtime 调用 (claude_node)
3. 结果打包输出 (output: json)

### Issue 3: models.providers 未被使用
`claude-node-cli` 在 models.providers 中指向已删除的 18793 服务，所以即使想用 provider 通道也行不通

### Issue 4: daemon-pool 设计基于错误假设
- daemon-pool 设计假设 OpenClaw 支持 `input: http`
- **实际**: OpenClaw 只支持 `input: arg` 和 `input: stdin`
- **结论**: daemon-pool 的 HTTP daemon 架构无法通过 cliBackends 接入

---

## Correct Architecture

```
External Channel (Feishu / WeCom / ...)
        ↓
   OpenClaw Gateway
   [adapter only - 渠道接入/会话壳/生态壳]
        ↓
   models.providers (HTTP custom provider)
        ↓
   openclaw-claude-bridge  ← 新的薄 bridge 层
        ↓
   claude-node (ClaudeController / on_message / session)
        ↓
   Claude Code CLI
        ↓
   DB / Control Plane (阶段事件 / artifact / run_id)
        ↓
   Feishu Outbound (Notifier)
```

### 分层职责

| 层 | 职责 |
|----|------|
| OpenClaw Gateway | 外部接入、渠道适配、会话路由 |
| models.providers | 标准 OpenAI-compatible HTTP 接口 |
| bridge | 协议转换、session 映射、事件分发 |
| claude-node | Claude runtime、on_message 事件流、session 管理 |
| DB/Control Plane | run_id、stage、artifact、outbound events (source of truth) |
| Notifier | 阶段事件 → Feishu 卡片更新 |

---

## 下一步行动

### P0 (立即)
1. **验证现状**: 确认当前请求确实走 cliBackends
2. **新建 bridge**: 实现 `/v1/chat/completions` 接口（不是 daemon 模式）
3. **更新 provider 配置**: 指向新的 bridge 服务

### P1
1. 实现 notifier 产生阶段事件
2. 分离 wrapper.py 职责
3. 实现 run_id → feishu_context 映射
4. **daemon-pool 设计需重构**：不能通过 cliBackends 接入 HTTP daemon

### P2
1. 清理废弃配置
2. 归档完成的工作
