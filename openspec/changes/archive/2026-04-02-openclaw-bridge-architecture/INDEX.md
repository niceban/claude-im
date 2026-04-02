# Archive Index — 2026-04-02 OpenClaw Bridge Architecture

## 归档时间
2026-04-02

## 归档原因
确立正确的 OpenClaw + claude-node 集成架构，废弃基于错误假设的 daemon-pool 方案。

---

## 主要归档内容

### 1. ARCHITECTURE.md（新建）
**内容**：完整的架构设计文档
**状态**：已确认

### 2. daemon-pool 任务归档
**原路径**：`openspec/changes/claude-node-cli-daemon-pool/`
**归档路径**：`openspec/changes/archive/2026-04-02-openclaw-bridge-architecture/daemon-pool-archive/`

**归档原因**：
- Task 5.1、5.2 假设 `input: http` 存在，但 CliBackendSchema 实际不支持
- daemon-pool 设计基于错误前提

**关键冲突**：
```markdown
## tasks.md 中冲突的任务

### 5.1 更新 cliBackends 的 input 从 arg 改为 HTTP 模式
❌ 错误：CliBackendSchema 只支持 arg 和 stdin，不支持 http

### 5.2 更新 command/args 指向 daemon 监听地址
❌ 错误：cliBackends 不支持 HTTP 模式作为 input
```

### 3. OpenClaw 路由研究归档
**原路径**：`.workflow/.team/RV-openclaw-arch-review-20260402/`
**归档路径**：`openspec/changes/archive/2026-04-02-openclaw-bridge-architecture/routing-research/`

---

## 冲突文档清单

| 原文档 | 冲突类型 | 冲突内容 |
|--------|----------|----------|
| `claude-node-cli-daemon-pool/tasks.md` 5.1, 5.2 | 前提错误 | 假设 `input: http` 存在 |
| `claude-node-cli-daemon-pool/proposal.md` | 架构错误 | daemon-pool 通过 cliBackends 接 HTTP daemon |
| `claude-node-cli-daemon-pool/design.md` | 架构错误 | 同上 |

---

## 新架构要点

1. **OpenClaw 做面子**：渠道接入、会话管理、外部生态
2. **claude-node 做里子**：Claude Runtime、事件流、Session 控制
3. **正确路径**：models.providers + bridge，不是 cliBackends
4. **100% bridge**：默认切换到 bridge，不做灰度
