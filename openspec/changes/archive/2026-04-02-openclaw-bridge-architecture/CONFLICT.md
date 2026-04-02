# 冲突文档总结

## 归档时间
2026-04-02

## 归档的冲突文档

### 1. claude-node-cli-daemon-pool（完整归档）

**原路径**：`openspec/changes/claude-node-cli-daemon-pool/`

**冲突类型**：架构设计基于错误前提

**核心错误**：

#### 错误假设：cliBackends 支持 `input: http`

```markdown
# tasks.md 中的错误任务

## 5.1 更新 ~/.openclaw/openclaw.json
❌ 错误：cliBackends 的 input 从 "arg" 改为 HTTP 模式

## 5.2 更新 command/args 指向 daemon 监听地址
❌ 错误：cliBackends 不支持 HTTP 模式
```

**实际情况**：
```typescript
// CliBackendSchema (zod-schema.core.d.ts)
// input 字段只支持 "arg" 和 "stdin"
input: z.union([z.literal("arg"), z.literal("stdin")]).optional()
```

**影响**：
- Phase 5 任务（5.1、5.2、5.3）全部无法完成
- daemon-pool 设计无法通过 cliBackends 接入

---

### 2. 错误理解纠正

#### 错误理解 1："text-only fallback" 描述 cliBackends

**错误**：cliBackends 是 "text-only fallback"

**纠正**：
- "text-only fallback" 是 OpenRouter 模型能力查找时的降级策略
- 与 cliBackends 能力边界无关
- 来源：Issue #45867

#### 错误理解 2：cliBackends 不支持 tools/streaming

**错误**：cliBackends 只能做 text-only

**纠正**：
- cliBackends 实际上支持 tools 和 streaming
- 但生产配置用 `CLAUDE_STREAM_EVENTS: false` 禁用了 streaming
- 原因是 JSONL vs JSON 输出格式不匹配

---

## 归档后的状态

| 文档 | 状态 |
|------|------|
| daemon-pool/tasks.md | 已归档（Phase 5 任务无法完成）|
| daemon-pool/proposal.md | 已归档（基于错误前提）|
| daemon-pool/design.md | 已归档（基于错误前提）|

---

## 正确架构

```
Feishu → OpenClaw Gateway → models.providers → bridge → claude-node → Claude CLI
                              [主路径]
```

**关键变更**：
1. 使用 `models.providers` 而不是 `cliBackends` 作为主路径
2. 实现 bridge 服务提供 OpenAI-compatible 接口
3. 100% 流量走 bridge（不做灰度）
