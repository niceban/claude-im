# 归档：OpenClaw + claude-node 集成架构结论

## 归档日期
2026-04-02

## 归档类型
研究结论归档 + 冲突文档归档

---

## 一、核心结论

### 1.1 路由解析

**当前 model ref**: `claude-node-cli/MiniMax-M2.7`

**实际解析路径**: `cliBackends.claude-node-cli` → wrapper.py → claude_node → Claude CLI

**来源**: OpenClaw 解析 cliBackends 时，provider 前缀匹配 `agents.defaults.cliBackends` 中的 key

### 1.2 关键发现：cliBackends 是 text-only fallback

| 维度 | models.providers | cliBackends |
|------|-----------------|-------------|
| 通信方式 | HTTP 请求 | stdin/CLI 参数 |
| 场景 | 云 API / 本地 HTTP 服务 | 本地 CLI agent |
| tools 支持 | ✅ 支持 | ❌ 不支持 (text-only fallback) |
| streaming | ✅ 支持 | ❌ 不支持 |
| OpenClaw tools | ✅ 支持 | ❌ 禁用 |

**官方定义**: CLI backends 是 "safety-net rather than a primary path"

### 1.3 关键发现：OpenClaw 不支持 `input: http`

```typescript
// OpenClaw CliBackendSchema
input: z.union([z.literal("arg"), z.literal("stdin")]).optional()
// 只有 "arg" 和 "stdin"，没有 "http"
```

### 1.4 正确架构

```
External Channel (Feishu)
        ↓
   OpenClaw Gateway
   [adapter only - 渠道接入/会话壳/生态壳]
        ↓
   models.providers (HTTP custom provider) ← 新主链路
        ↓
   openclaw-claude-bridge  ← 新薄 bridge 层
        ↓
   claude-node (ClaudeController / on_message / session)
        ↓
   Claude Code CLI
        ↓
   DB / Control Plane (阶段事件 / artifact / run_id)
        ↓
   Feishu Outbound (Notifier)
```

### 1.5 分层职责

| 层 | 职责 |
|----|------|
| OpenClaw Gateway | 外部接入、渠道适配、会话路由 |
| models.providers | 标准 OpenAI-compatible HTTP 接口 |
| bridge | 协议转换、session 映射、事件分发 |
| claude-node | Claude runtime、on_message 事件流、session 管理 |
| DB/Control Plane | run_id、stage、artifact、outbound events (source of truth) |
| Notifier | 阶段事件 → Feishu 卡片更新 |

### 1.6 models.providers 配置示例

```json
{
  "models": {
    "providers": {
      "claude-bridge": {
        "baseUrl": "http://127.0.0.1:8787/v1",
        "apiKey": "local-dev",
        "api": "openai-completions",
        "models": [{
          "id": "MiniMax-M2.7",
          "name": "Claude via claude-node",
          "contextWindow": 200000,
          "supportsTools": true
        }]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "claude-bridge/MiniMax-M2.7"
      }
    }
  }
}
```

---

## 二、与之前设计的冲突

### 2.1 daemon-pool 设计冲突

| 文档 | 冲突内容 | 状态 |
|------|----------|------|
| `proposal.md` | `input: arg` → `input: http` | ❌ 不可能实现 |
| `design.md` Risk | "HTTP 模式与设想不兼容" | ✅ 已被证实 |
| `tasks.md` 5.1 | 更新 input 为 HTTP 模式 | ❌ 无法完成 |
| `tasks.md` 5.2 | command/args 指向 daemon 地址 | ❌ 架构错误 |

### 2.2 冲突原因

daemon-pool 设计假设：
```
OpenClaw cliBackends → HTTP daemon
```

实际情况：
```
OpenClaw cliBackends → 只能走 stdin/arg → wrapper.py
OpenClaw models.providers → HTTP → bridge → claude-node (可行)
```

### 2.3 CLI 能力 vs Provider 能力

| 能力 | cliBackends | models.providers + bridge |
|------|-------------|--------------------------|
| 工具调用 | ❌ | ✅ |
| 流式事件 | ❌ | ✅ |
| 长会话 | ✅ | ✅ |
| Skills/Slash commands | ❌ | ✅ |

---

## 三、最小改动方案

### P0 (立即)
1. **实现 bridge 服务**：FastAPI/Node 实现 `/v1/chat/completions` 接口，内部调用 claude_node
2. **更新 openclaw.json**：新增 models.providers 指向 bridge
3. **保持 cliBackends**：作为 fallback 保底

### P1
1. 实现 notifier 产生阶段事件
2. 实现 run_id → feishu_context 映射
3. daemon-pool 设计需重构

### P2
1. 清理废弃配置（clawrelay_bridge 相关）
2. 归档完成的工作

---

## 四、External Resources

- OpenClaw CliBackendSchema: `openclaw/src/config/zod-schema.core.ts`
- Provider 配置示例: `Light-Heart-Labs/DreamServer/openclaw.json`
- Ollama 配置: `models.providers.ollama`
