## Context

当前生产架构：
```
Feishu → OpenClaw Gateway → cliBackends → wrapper.py → claude-node → Claude CLI
```

cliBackends 是 "text-only fallback"（官方定义），被错误地当作主执行路径。问题：
- `input: http` 根本不存在（CliBackendSchema 只有 arg/stdin）
- 阶段事件不可见
- streaming 被禁用
- wrapper.py 三合一职责

目标架构：
```
Feishu → OpenClaw Gateway → models.providers → bridge → claude-node → Claude CLI
```

## Goals / Non-Goals

**Goals:**
- 实现 OpenClaw 面子（渠道接入）+ claude-node 里子（Runtime）的正确分层
- 通过 `models.providers` + bridge 实现 OpenAI-compatible HTTP 接口
- 通过 canary 策略渐进切换流量（不做 100% 立即切换）
- TDD 开发：每个模块独立测试后再进入下一模块

**Non-Goals:**
- 不修改 OpenClaw Core
- 不废弃 cliBackends（降级为 fallback 保留）
- 不实现阶段事件语义（由上层 control-plane 负责）

## Decisions

### Decision 1: HTTP 框架选择 Starlette

**选择**：Starlette（同步模式）

**理由**：
- 轻量级，比 FastAPI 少依赖
- 同步模式足够（claude-node 调用是同步的）
- uvicorn 支持热重载

**替代方案**：
- FastAPI：更重，但有自动 OpenAPI 文档
- Flask：更老派，但稳定

### Decision 2: Session 管理策略

**选择**：内存 Map + LRU 驱逐

**理由**：
- 最小实现复杂度
- 符合 claude-node 内部 session 管理能力
- 服务重启 session 丢失是可接受的风险

**替代方案**：
- Redis 持久化：更稳定但增加运维复杂度
- PostgreSQL：过度设计

### Decision 3: Bridge 不做 Session 池化

**选择**：Session 生命周期由 claude-node 内部管理

**理由**：
- claude-node 已有成熟的 session 管理（fork/resume）
- Bridge 只做协议转换，不做业务逻辑
- 保持 Bridge 薄而简单

**替代方案**：
- Bridge 内置 SessionPool：增加复杂度，不符合薄层原则

### Decision 4: 不实现 Streaming 响应

**选择**：先实现非 streaming，后续迭代

**理由**：
- OpenClaw models.providers 的 streaming 支持需要验证
- 非 streaming 是最小可行版本（MVP）
- 阶段事件可以通过旁路（notifier）传递

**替代方案**：
- 同时实现 streaming：增加复杂度

### Decision 5: Canary 流量切换策略

**选择**：渐进式 canary 切换（1% → 10% → 50% → 100%）

| 阶段 | 流量比例 | 验证目标 |
|------|----------|----------|
| Phase 1 | 1% | 基础功能验证 |
| Phase 2 | 10% | 错误率和延迟对比 |
| Phase 3 | 50% | 长时间稳定性 |
| Phase 4 | 100% | 全量切换 |

**理由**：
- Alpha 状态 claude-node 存在不确定性
- 保留 cliBackends 作为即时回滚目标
- 每阶段观察期：至少 24 小时或 1000 请求

**替代方案**：
- 100% 直接切换：风险高，回滚需要改配置
- A/B 测试：增加复杂度，当前阶段不需要

### Decision 6: API Key 认证方案

**选择**：X-API-Key header 认证

**理由**：
- 与 OpenAI API 兼容
- 简单易实现
- OpenClaw Gateway 可以传递认证信息

**实现**：
- Bridge 校验 `X-API-Key` header
- 无效或缺失返回 401
- Key 存储在环境变量或配置文件

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| OpenClaw provider 路由不稳定 | 先测试环境验证 |
| claude-node Alpha 状态 | 固定版本，避免升级 |
| Session 重启丢失 | 可接受的短期限制 |
| JSONL vs JSON 格式不匹配 | 非 streaming 避免此问题 |

## Migration Plan

1. **Phase 1**: 实现 bridge 服务核心（/v1/chat/completions, /health, /v1/models）
2. **Phase 2**: 配置 models.providers 指向 bridge（1% canary）
3. **Phase 3**: 端到端测试 + 逐步扩大 canary（10% → 50%）
4. **Phase 4**: 切换 100% 流量

**回滚方案**：将 openclaw.json 中的 `agents.defaults.model.primary` 改回 cliBackends 配置，或逐步降低 canary 比例

## Open Questions

1. OpenClaw provider 的 streaming 行为是否与 SSE 兼容？
2. 是否需要实现 `completion_start` 等阶段事件旁路？
3. cliBackends fallback 何时可以完全废弃？
