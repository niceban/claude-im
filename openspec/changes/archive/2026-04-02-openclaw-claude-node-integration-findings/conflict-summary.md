# 冲突文档汇总

## 冲突概述

本次研究发现了之前设计中的关键错误：daemon-pool 设计假设 OpenClaw 支持 `input: http` 模式，但实际 OpenClaw **只支持 `arg` 和 `stdin` 两种 input 模式**。

---

## 冲突文档列表

### 1. daemon-pool/proposal.md

| 位置 | 错误内容 | 正确内容 |
|------|----------|----------|
| "What Changes" | `input: arg` → `input: http` | **不可能实现** - OpenClaw 不支持 http 模式 |
| "BREAKING" 变更 | OpenClaw 配置变更为 `input: http` | **无法完成** |

### 2. daemon-pool/design.md

| 位置 | 错误内容 | 正确内容 |
|------|----------|----------|
| Decision 5 | 输入解析 - HTTP 模式 | **不存在** - 只有 arg/stdin |
| Risk | "OpenClaw 的 `input: http` 模式与设想不兼容" | **已被证实** - 确实不可能 |
| Non-Goals | "不实现 WebSocket 流式（当前 OpenClaw cliBackends HTTP 模式不支持）" | 正确，但问题在于 **整个 HTTP 思路就是错的** |

### 3. daemon-pool/tasks.md

| 任务 | 状态 | 说明 |
|------|------|------|
| 1.7 评估 session_manager.py | 待定 | 与新架构无关 |
| 5.1 更新 input 为 HTTP 模式 | ❌ **无法完成** | OpenClaw 不支持 |
| 5.2 更新 command/args 指向 daemon | ❌ **无法完成** | 架构错误 |
| 5.3 测试 daemon HTTP 与 OpenClaw 集成 | ❌ **无法完成** | 架构错误 |

---

## 冲突原因分析

### 原始假设

daemon-pool 设计假设通过 cliBackends 的 HTTP 模式接入 daemon：
```
OpenClaw cliBackends (input: http) → daemon HTTP server → claude_node
```

### 实际情况

OpenClaw cliBackends 只支持两种 input 模式：
1. `input: arg` - 将 prompt 作为最后一个 CLI 参数
2. `input: stdin` - 通过标准输入传递 prompt

**正确的做法**应该是使用 `models.providers` 而不是 cliBackends：
```
OpenClaw models.providers (HTTP) → bridge HTTP → claude_node
```

---

## 需要修改的文档

1. **daemon-pool/proposal.md** - 需重写，改为通过 models.providers 接入
2. **daemon-pool/design.md** - 需重构，删除 HTTP input 相关设计
3. **daemon-pool/tasks.md** - Phase 5 任务需重新设计或删除
4. **CLAUDE.md** - 需更新架构图，反映正确的分层

---

## 正确的 daemon 设计思路

如果仍想实现 daemon（session pool 热启动），正确的架构是：

### 方案 A: 通过 models.providers 接入

```
OpenClaw Gateway → models.providers → bridge (HTTP) → daemon (claude_node session pool)
```

bridge 作为 HTTP 服务，接收 OpenClaw provider 的标准请求，内部维护 session pool。

### 方案 B: 保持 cliBackends 但优化冷启动

不改变接入方式，但优化 wrapper.py 的冷启动时间（如预热、缓存等）。

---

## 建议

1. **归档** daemon-pool 当前的 Phase 1-4 代码（session pool 逻辑仍然有价值）
2. **重写** Phase 5，改为通过 models.providers 接入
3. **更新** CLAUDE.md 反映正确的架构
