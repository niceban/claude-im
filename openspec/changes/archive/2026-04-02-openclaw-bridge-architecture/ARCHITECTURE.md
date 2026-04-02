# OpenClaw 面子 + claude-node 里子 架构设计文档

**版本**: 1.0
**日期**: 2026-04-02
**状态**: 已确认
**优先级**: P0

---

## 1. 核心结论

### 1.1 架构定位

| 组件 | 角色 | 定位 |
|------|------|------|
| **OpenClaw** | 面子（外部生态接入层） | 渠道接入、会话管理、外部生态适配 |
| **claude-node** | 里子（Claude Runtime 核心） | Claude CLI 进程管理、事件流、Session 控制 |
| **openclaw-claude-bridge** | 协议转换层 | HTTP ↔ ClaudeController 适配 |

### 1.2 正确架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     External Channel (Feishu)                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      OpenClaw Gateway                                │
│                   [Adapter / 渠道接入层]                             │
│                                                                     │
│  - 飞书 WebSocket 长连接                                            │
│  - Session / 会话路由                                               │
│  - Auth / 鉴权                                                      │
│  - models.providers 配置管理                                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   models.providers                                   │
│              [HTTP Custom Provider 接口]                             │
│                                                                     │
│  - baseUrl: http://127.0.0.1:18792                                 │
│  - api: "openai-completions"                                        │
│  - OpenAI-compatible /v1/chat/completions                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 openclaw-claude-bridge                              │
│                   [薄协议转换层]                                     │
│                                                                     │
│  职责：                                                             │
│  - /v1/chat/completions (OpenAI-compatible)                        │
│  - /v1/models                                                       │
│  - /health                                                          │
│  - Session 映射管理                                                 │
│  - 协议转换 (HTTP ↔ ClaudeController)                                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      claude-node                                     │
│                   [Claude Runtime 核心]                             │
│                                                                     │
│  - ClaudeController (进程管理)                                      │
│  - on_message (实时事件流)                                         │
│  - Session / fork / transcript                                      │
│  - Tools / Streaming 完整支持                                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Claude Code CLI                                 │
│                    [真正的 Autonomous Agent]                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 组件职责边界

### 2.1 OpenClaw Gateway（面子）

**职责**：
- 渠道接入（飞书、Slack、Telegram、Webhook）
- WebSocket 长连接管理
- Session 路由和生命周期管理
- Auth/鉴权
- models.providers 配置

**不负责**：
- Claude Runtime 内部逻辑
- Session 池化管理
- 阶段事件语义
- 任务状态机

### 2.2 openclaw-claude-bridge（协议转换）

**职责**：
- 实现 `/v1/chat/completions` (OpenAI-compatible)
- 实现 `/v1/models`
- 实现 `/health`
- Session 映射管理
- HTTP 请求 → ClaudeController 调用转换

**不负责**：
- Session 池化（由 claude-node 内部处理）
- 阶段事件语义定义
- 业务状态机

### 2.3 claude-node（Runtime 核心）

**职责**：
- ClaudeController 生命周期管理
- on_message 事件捕获
- Session 管理（fork/resume/transcript）
- Tools/Streaming 能力

**不负责**：
- HTTP 协议处理
- OpenClaw 适配

---

## 3. OpenClaw 能力边界

### 3.1 支持的能力

| 能力 | 状态 | 备注 |
|------|------|------|
| 渠道接入 | ✅ 完整 | 飞书 WebSocket、Slack、Telegram |
| 会话管理 | ✅ 完整 | session/routing/auth |
| Gateway 控制面 | ✅ 完整 | WebSocket 长连接 |
| models.providers | ✅ 支持 | OpenAI-compatible HTTP provider |
| cliBackends | ⚠️ fallback | text-only，不支持 http input |

### 3.2 不支持的能力

| 能力 | 状态 | 备注 |
|------|------|------|
| cliBackends input: http | ❌ 不支持 | Schema 只有 arg/stdin |
| 阶段事件 streaming | ⚠️ 限制 | deliver() 只在 final 触发 |

### 3.3 关键发现

**CliBackendSchema 定义**（源码确认）：
```typescript
input: z.union([z.literal("arg"), z.literal("stdin")]).optional()
// 只有 "arg" 和 "stdin"，没有 "http"
```

**"text-only fallback" 真实含义**：
- 是 OpenRouter 模型的降级策略
- 与 cliBackends 能力边界无关
- 来源：Issue #45867

---

## 4. claude-node 能力边界

### 4.1 核心能力

| 能力 | 状态 | 备注 |
|------|------|------|
| ClaudeController | ✅ | 管理 Claude CLI 进程 |
| on_message | ✅ | 实时捕获 assistant/tool_result/result 事件 |
| Session 管理 | ✅ | session_id/fork/resume/transcript |
| Tools 调用 | ✅ | 完整支持 |
| Streaming | ✅ | 支持 |

### 4.2 限制

| 限制 | 说明 |
|------|------|
| 不直接暴露 HTTP | 需要 bridge 层 |
| _send_lock | 同一 controller 不能并发 send |
| Alpha 状态 | 可能 breaking change |

---

## 5. 接入路径对比

### 5.1 错误路径（当前生产）

```
Feishu → OpenClaw Gateway → cliBackends → wrapper.py → claude-node → Claude CLI
                              [text-only fallback]
                              [三合一职责]
```

**问题**：
- cliBackends 被当成主路径（应该是 fallback）
- wrapper.py 承担太多职责
- 阶段事件不可见

### 5.2 正确路径（目标）

```
Feishu → OpenClaw Gateway → models.providers → bridge → claude-node → Claude CLI
                              [主路径]
                              [薄协议转换]
```

**优势**：
- 架构分层正确
- 阶段事件可透传
- 职责清晰

---

## 6. Bridge 服务接口定义

### 6.1 POST /v1/chat/completions

**Request**：
```json
{
  "model": "claude-sonnet-4-6",
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "max_tokens": 8192,
  "stream": false,
  "temperature": 1.0
}
```

**Response（非 streaming）**：
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "claude-sonnet-4-6",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！有什么可以帮助你的吗？"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

### 6.2 GET /health

**Response**：
```json
{
  "status": "healthy",
  "timestamp": 1234567890,
  "version": "1.0.0"
}
```

### 6.3 GET /v1/models

**Response**：
```json
{
  "object": "list",
  "data": [
    {
      "id": "claude-sonnet-4-6",
      "object": "model",
      "created": 1234567890,
      "name": "Claude Sonnet 4",
      "context_window": 200000
    }
  ]
}
```

---

## 7. OpenClaw 配置

### 7.1 models.providers 配置

```json
{
  "models": {
    "providers": {
      "claude-bridge": {
        "baseUrl": "http://127.0.0.1:18792",
        "apiKey": "local-dev",
        "api": "openai-completions",
        "models": [
          {
            "id": "claude-sonnet-4-6",
            "name": "Claude Sonnet 4",
            "contextWindow": 200000,
            "maxTokens": 8192
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "claude-bridge/claude-sonnet-4-6"
      }
    }
  }
}
```

### 7.2 迁移策略

**100% bridge（默认）**：
- 直接切换到 models.providers
- cliBackends 保留作为 fallback（可选废弃）

---

## 8. 实现步骤

### Phase 1: Bridge 核心实现
- [ ] 实现 `/v1/chat/completions`
- [ ] 实现 `/health`
- [ ] 实现 `/v1/models`
- [ ] 集成 claude-node

### Phase 2: 配置更新
- [ ] 更新 openclaw.json
- [ ] 验证 models.providers 路由

### Phase 3: 联调测试
- [ ] 端到端测试
- [ ] 飞书集成测试

---

## 9. 关键源码引用

### 9.1 OpenClaw 路由解析

**isCliProvider()** (`model-selection-CMtvxDDg.js:85-90`)：
```javascript
function isCliProvider(provider, cfg) {
  const backends = cfg?.agents?.defaults?.cliBackends ?? {};
  return Object.keys(backends).some((key) => normalizeProviderId(key) === normalized);
}
```

### 9.2 CliBackendSchema

**input 字段** (`zod-schema.core.d.ts:479-517`)：
```typescript
input: z.ZodOptional<z.ZodUnion<readonly [z.ZodLiteral<"arg">, z.ZodLiteral<"stdin">]>>
```

---

## 10. 相关文档

- [cliBackends 源码分析](./evidence/cliBackends-source.md)
- [models.providers 配置示例](./evidence/models-providers-config.md)
- [Issue #57326](./evidence/issue-57326.md)
- [Issue #45867](./evidence/issue-45867.md)
