## Context

### 背景

当前 `clawrelay-feishu-server` 存在多层耦合：Feishu 消息通道、Python Bridge (claude-node)、SessionManager、OpenClaw Gateway Client 全部混在一起。维护和扩展困难。

OpenClaw 原生提供：
- 24+ 消息通道（Feishu、Discord、Slack 等）
- Gateway WebSocket 协议（ws://127.0.0.1:18789）
- Provider 插件系统（支持自定义 AI 引擎）

claude-node 提供：
- Claude CLI subprocess 管理
- Session 生命周期管理
- 流式事件支持（stream-json over stdin/stdout）

### 约束

- 不修改 OpenClaw 源码，使用官方 Provider 插件机制
- 不修改 claude-node 源码，使用其现有 API
- v1 先实现阻塞版本，HTTP streaming 后期扩展
- OpenClaw 默认静默，仅在 claude-node 宕机时作为 Fallback 上线

## Goals / Non-Goals

**Goals:**
- OpenClaw 作为通讯层（消息路由、通道管理）
- claude-node 作为 AI 处理层（Claude CLI 管理）
- 最小化 Bridge 代码，利用现有 claude-node 组件
- 支持 Fallback 机制（健康检查 + 故障切换）

**Non-Goals:**
- 不实现 HTTP streaming（v2 后期再做）
- 不修改 OpenClaw 源码
- 不修改 claude-node 源码
- Dashboard 集成（后期讨论）

## Decisions

### Decision 1: 使用 OpenClaw Provider 插件机制接入 claude-node

**选择**: 通过 `models.providers` 配置 claude-node Bridge HTTP API

**原因**:
- 官方支持的扩展方式，无需魔改源码
- 与现有 30+ Provider 机制一致
- 配置化，易于维护

**Alternatives considered**:
- Protocol Bridge（拦截 Gateway WebSocket 流量）：复杂度高，需要完整实现协议转换
- Fork OpenClaw 替换 Pi Agent：维护成本极高，无法跟进更新

**配置格式**:
```json5
{
  models: {
    mode: "merge",
    providers: {
      "claude-node": {
        baseUrl: "http://127.0.0.1:18792",
        apiKey: "not-needed",
        api: "openai-completions",
        models: [
          {
            id: "claude-sonnet-4-6",
            name: "Claude Sonnet 4",
            input: ["text"],
            contextWindow: 200000,
            maxTokens: 8192,
          },
        ],
      },
    },
  },
}
```

### Decision 2: Python Bridge Server 作为 HTTP API Wrapper

**选择**: 新建 `clawrelay-bridge/` 目录，实现 HTTP Server 封装 claude-node

**原因**:
- OpenAI-compatible API 格式与 OpenClaw Provider 匹配
- 复用现有 `ClaudeNodeAdapter` 代码
- 职责单一：只做协议转换

**API Endpoint 设计**:
```
POST /v1/chat/completions  (blocking, v1)
GET  /health               (健康检查)
GET  /v1/models            (模型列表)
```

**请求格式** (OpenAI-compatible):
```json
{
  "model": "claude-sonnet-4-6",
  "messages": [{"role": "user", "content": "..."}],
  "max_tokens": 8192
}
```

**响应格式** (blocking v1):
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "claude-sonnet-4-6",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "..."},
    "finish_reason": "stop"
  }]
}
```

### Decision 3: Session Mapping 实现 1:1 映射

**选择**: SQLite 表 `session_mapping` 实现 OpenClaw session ↔ claude-node session 对应

**表结构**:
```sql
CREATE TABLE session_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    openclaw_session_id TEXT UNIQUE,    -- OpenClaw Gateway session ID
    claude_session_id TEXT UNIQUE,      -- claude-node relay session ID
    platform TEXT,                       -- 来源平台 (feishu/discord/slack)
    user_id TEXT,                        -- 平台用户 ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    status TEXT DEFAULT 'active'         -- active | paused | archived
);
```

**原因**:
- 简单直接，1:1 映射符合当前架构
- 复用现有 SessionManager 的 SQLite 基础设施
- 便于追踪和调试

### Decision 4: Fallback 机制通过健康检查触发

**选择**: Bridge Server 内置 Health Monitor，OpenClaw 通过 Skill 调用检测

**原因**:
- 不修改 OpenClaw 源码（官方无 Fallback 插件机制）
- Skill 可调用外部服务检查健康状态
- 可扩展为更复杂的故障切换策略

**健康检查流程**:
```
1. Bridge Server 定期检查 claude-node 状态
2. 如果 claude-node 无响应 → 标记为 unhealthy
3. OpenClaw Skill 调用 Bridge API 获取状态
4. 如果 unhealthy → OpenClaw 激活维修
5. claude-node 恢复 → OpenClaw 立即下线
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| OpenClaw Provider 不支持流式响应 | v1 先用阻塞版本，streaming 后期扩展 |
| claude-node 阻塞 send() 导致 Bridge 挂起 | 使用 asyncio + thread pool executor |
| Session 映射表成为单点故障 | SQLite 持久化，支持重启恢复 |
| OpenClaw 与 claude-node 会话状态不同步 | 定期同步 last_active 时间戳 |

## Migration Plan

### Phase 1: 基础设施
1. 创建 `clawrelay-bridge/` 目录结构
2. 迁移 `ClaudeNodeAdapter` 相关代码
3. 实现 HTTP Server (blocking v1)
4. 实现 Session Mapping 表

### Phase 2: OpenClaw 集成
1. 配置 `openclaw.json` Provider
2. 测试 OpenClaw → Bridge → claude-node 链路
3. 验证 session mapping 正确工作

### Phase 3: Fallback 机制
1. 实现 Health Monitor
2. 创建 OpenClaw Skill 调用健康检查
3. 测试故障切换流程

### Phase 4: 归档
1. 归档 `clawrelay-feishu-server/` → `archive/`
2. 归档 `clawrelay-report/` → `archive/`
3. 更新文档

## Open Questions

1. **HTTP Streaming**: v2 实现，方案待定（Server-Sent Events 或 WebSocket）
2. **多 claude-node 实例**: 未来可能需要连接池或负载均衡
3. **Dashboard 集成**: 后期讨论，会话状态管理方案待定
