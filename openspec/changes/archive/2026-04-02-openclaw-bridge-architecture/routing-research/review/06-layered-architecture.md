# Layered Architecture Review

## Verdict: PARTIALLY_SOUND

The proposed "Correct Architecture" is **architecturally sound** — layers are properly defined and responsibilities are clear. However, the **current production architecture is unsound** because it uses cliBackends (a text-only fallback mechanism) as the primary execution path, fundamentally violating the intended layering.

---

## Layer Analysis

### Correct Architecture (Target)

```
External Channel (Feishu / WeCom / ...)
        ↓
   OpenClaw Gateway          [adapter only - 渠道接入/会话壳/生态壳]
        ↓
   models.providers           [HTTP custom provider - 标准 OpenAI-compatible 接口]
        ↓
   openclaw-claude-bridge     [薄 bridge 层 - 协议转换/session 映射/事件分发]
        ↓
   claude-node                [Claude runtime - on_message 事件流/session 管理]
        ↓
   Claude Code CLI
        ↓
   DB/Control Plane           [run_id/stage/artifact/outbound events - source of truth]
        ↓
   Feishu Outbound (Notifier) [阶段事件 → Feishu 卡片更新]
```

### Current Architecture (Production - WRONG)

```
Feishu → OpenClaw Gateway → cliBackends → wrapper.py → claude_node → Claude CLI
                                              [text-only fallback]
                                              [三合一: 协议适配 + runtime调用 + 结果打包]
```

---

## Layer Responsibilities

| Layer | Assigned | Actual (Correct) | Actual (Current) | Match? |
|-------|----------|------------------|-------------------|--------|
| OpenClaw Gateway | 外部接入、渠道适配、会话路由 | 外部接入、渠道适配、会话路由 | 外部接入、渠道适配 | **YES** (correct) |
| models.providers | 标准 OpenAI-compatible HTTP 接口 | 标准 OpenAI-compatible HTTP 接口 | **NOT USED** (points to deleted 18793) | **NO** (current) |
| bridge | 协议转换、session 映射、事件分发 | 协议转换、session 映射、事件分发 | **MISSING** (replaced by wrapper.py) | **NO** (current) |
| claude-node | Claude runtime、on_message 事件流、session 管理 | Claude runtime、on_message 事件流、session 管理 | 部分使用（但通过 wrapper.py 间接调用） | **PARTIAL** |
| DB/Control Plane | run_id、stage、artifact、outbound events (source of truth) | run_id、stage、artifact、outbound events (source of truth) | **NOT IMPLEMENTED** | **NO** |
| Notifier | 阶段事件 → Feishu 卡片更新 | 阶段事件 → Feishu 卡片更新 | **NOT IMPLEMENTED** | **NO** |

---

## Coupling Analysis

### Correct Architecture Coupling: **SOUND**

| Interface | Coupling | Assessment |
|-----------|----------|------------|
| Gateway → models.providers | HTTP (OpenAI-compatible) | **Loose coupling** - Gateway 不关心 bridge 实现 |
| models.providers → bridge | HTTP /v1/chat/completions | **Loose coupling** - 标准协议接口 |
| bridge → claude-node | Internal function call (on_message) | **Controlled coupling** - bridge 知道 claude-node API |
| claude-node → Claude CLI | subprocess spawn | **Natural coupling** - 运行时依赖 |
| claude-node → DB/Control Plane | DB queries | **Natural coupling** - 状态持久化 |
| DB/Control Plane → Notifier | Event emission | **Event-driven** - 很好的解耦 |

### Current Architecture Coupling: **UNSOUND**

| Interface | Coupling | Assessment |
|-----------|----------|------------|
| Gateway → cliBackends | CLI stdin/args | **Tight coupling** - 能力受限 |
| wrapper.py (三合一) | Mixed | **Violates SRP** - 协议适配 + runtime + 打包混合 |

**Key Problem**: cliBackends 是"text-only fallback"，不应该作为主路径。cliBackends 设计用于 safety-net，不是 primary path。

---

## Issues Found

### Critical

1. **cliBackends 作为主路径** — cliBackends 设计为 "text-only fallback" / "safety-net rather than a primary path"，不支持 tools, streaming events, OpenClaw tools integration

2. **wrapper.py 三合一职责** — wrapper.py 同时承担:
   - OpenClaw 协议适配 (cliBackends 接口)
   - Claude runtime 调用 (claude_node)
   - 结果打包输出 (output: json)
   违反单一职责原则

3. **models.providers 指向废弃服务** — `models.providers.claude-node-cli` 指向已删除的 18793 服务，即使想用 provider 通道也行不通

4. **daemon-pool 设计基于错误假设** — 假设 OpenClaw 支持 `input: http`，但实际只支持 `input: arg` 和 `input: stdin`

### Moderate

5. **DB/Control Plane 缺失** — 没有实现 run_id → feishu_context 映射，无法做阶段事件追踪

6. **Notifier 缺失** — 没有实现阶段事件 → Feishu 卡片更新

7. **sessionIdFields 临时补丁** — 在 cliBackends 配置中添加 `sessionIdFields` 是权宜之计，不是架构解决方案

---

## Recommendation

### Immediate Fixes

1. **废弃 cliBackends 主路径** — 切换到 models.providers HTTP 通道

2. **新建 bridge 服务** — 实现 `/v1/chat/completions` 接口，作为薄协议转换层

3. **重构 wrapper.py** — 拆分为:
   - bridge (协议转换)
   - claude-node adapter (runtime 调用)

4. **重建 models.providers 配置** — 指向新的 bridge 服务（而不是删除的 18793）

### Architecture Principles Applied

| Principle | Status |
|-----------|--------|
| Single Responsibility | **VIOLATED** (wrapper.py 三合一) |
| Layer Isolation | **VIOLATED** (cliBackends 绕过 models.providers) |
| Dependency Inversion | **SOUND** (Gateway → HTTP → bridge → claude-node) |
| Interface Segregation | **SOUND** (每层有明确接口) |

### Layer Dependency Graph (Correct)

```
Feishu ← ← ← ← ← ← ← ← ← ← ← ← ← ← [Notifier]
  |                                        ↑
  ↓                                        |
Gateway                                  [DB/Control Plane]
  |                                        ↑
  ↓                                        |
[HTTTP /v1/chat/completions]              |
  |                                        |
  ↓                                        |
bridge ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
  |
  ↓
claude-node
  |
  ↓
Claude CLI
```

**Conclusion**: The correct architecture is well-designed. Production should be migrated to use models.providers + bridge + claude-node layering, with DB/Control Plane and Notifier added for stage events support.
