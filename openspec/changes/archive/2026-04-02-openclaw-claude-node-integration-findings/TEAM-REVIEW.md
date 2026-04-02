# 团队审查报告

**审查日期**: 2026-04-02
**审查团队**: 10 个并行 specialized agents
**审查目标**: `openspec/changes/archive/2026-04-02-openclaw-claude-node-integration-findings/`

---

## 总体评估

### Verdict: **PARTIALLY SOUND** — 需要修正

| 维度 | 评分 | 说明 |
|------|------|------|
| COR (正确性) | 3/10 | daemon-pool 核心假设（`input: http`）被证伪 |
| SEC (安全性) | 7/10 | 架构无明显安全问题，但新引入组件有攻击面 |
| PRF (性能) | 6/10 | 热 session 复用可降低延迟，但当前方案无法实现 |
| MNT (可维护性) | 5/10 | wrapper.py 三合一职责需拆分，改动范围可控 |

---

## 1. 路由解析分析 (01-routing.md)

**Verdict: CORRECT**

### 关键发现

`claude-node-cli/MiniMax-M2.7` 路由解析：
- Provider = `claude-node-cli` 在 `isCliProvider()` 中检查 `cfg.agents.defaults.cliBackends`
- 由于 `cliBackends["claude-node-cli"]` 存在，返回 `true`
- **路由通过 cliBackends，不是 models.providers**

### 证据

```javascript
// OpenClaw model-selection-CMtvxDDg.js
function isCliProvider(provider, cfg) {
  const backends = cfg?.agents?.defaults?.cliBackends ?? {};
  return Object.keys(backends).some((key) => normalizeProviderId(key) === normalized);
}
```

### 问题

1. **Schema 与实现不一致**: Schema 说 "text-only fallback"，但 wrapper.py 支持 tools 和 streaming
2. **这不是路由错误**: 是 OpenClaw 的文档不一致，不是分析错误

---

## 2. 能力边界分析 (02-capability-boundaries.md)

**Verdict: PARTIALLY_ACCURATE** — 需要修正

### 关键发现

**"text-only fallback" 表征是不准确的**！

| 能力 | cliBackends 实际支持 |
|------|---------------------|
| Tools | ✅ 支持 (wrapper.py line 246 传递 `CLAUDE_TOOLS`) |
| Streaming | ✅ 支持 (wrapper.py 有完整 `on_message` 回调) |
| Input 模式 | ❌ 只有 `arg` 和 `stdin` (无 `http`) |

### 真正的问题

- **输出格式不匹配**: OpenClaw 期望 `output: "json"` 单个 JSON，但 wrapper.py 输出 JSONL streaming
- **这是配置选择问题**: 生产环境设置 `CLAUDE_STREAM_EVENTS: false` 是为了解决格式不匹配，不是协议限制

### 修正建议

1. cliBackends **不是**本质上 "text-only"
2. 真正问题是输出格式兼容性 (JSONL vs JSON)
3. 如果修复 wrapper 输出格式，可以重新启用 streaming

---

## 3. 架构设计分析 (03-architecture.md)

**Verdict: SOUND** — 架构本身合理

### 分层评估

| 层 | 职责 | 评估 |
|----|------|------|
| OpenClaw Gateway | 渠道接入/会话壳 | ✅ 正确 |
| models.providers | HTTP OpenAI-compatible 接口 | ✅ 正确主路径 |
| bridge | 协议转换/session 映射 | ✅ 适当厚度 |
| claude-node | Runtime/on_message/session | ✅ 正确核心 |
| DB/Control Plane | run_id/stage/artifact | ✅ 架构合理 |
| Notifier | 阶段事件 → Feishu | ✅ 正确分离 |

### 优点

1. 符合 OpenClaw 设计理念
2. 分层清晰，职责明确
3. 通过 HTTP provider 解锁完整能力
4. Control Plane 外置保证持久化

### 问题

1. Bridge 韧性未明确 (无健康检查/重试)
2. Control Plane 单点故障风险
3. Notifier 事件传递机制未指定

---

## 4. daemon-pool 冲突分析 (04-daemon-pool-conflict.md)

**Verdict: ACCURATELY_IDENTIFIED** — 冲突正确识别

### 设计假设

daemon-pool 假设 OpenClaw 支持 `input: http`:
```
OpenClaw cliBackends (input: http) → daemon HTTP server → claude_node session pool
```

### 实际

```typescript
// OpenClaw CliBackendSchema
input: z.union([z.literal("arg"), z.literal("stdin")]).optional()
// 只有 "arg" 和 "stdin"，没有 "http"
```

### 冲突根因

daemon-pool 设计者混淆了两个不同的集成点：
- **cliBackends**: stdin/arg only，短生命周期进程
- **models.providers**: HTTP，长期运行服务器，正确 API 协议

### 建议

1. **归档 daemon-pool Phase 5** — 通过 cliBackends 接入 HTTP daemon 架构上不可能
2. **daemon.py session pool 代码有价值** — 池逻辑本身是正确的，只是接入路径错误
3. **替代方案**:
   - stdin 持久化: 保持 `input: stdin` 但让 wrapper 长期运行
   - models.providers: 完整 HTTP API 重新设计 (重大工作)

---

## 5. 最小改动方案分析 (05-minimum-change-plan.md)

**Verdict: PARTIALLY_FEASIBLE** — 部分可行

### 方案

**P0**: 实现 bridge + 更新 models.providers + 保持 cliBackends fallback

### 可行性

| 步骤 | 可行性 | 备注 |
|------|--------|------|
| 实现 bridge 服务 | 可能 | 需从零开始构建 |
| 更新 models.providers | 直接 | 标准 OpenClaw 配置 |
| 保持 cliBackends fallback | 安全 | 现有配置不变 |

### 问题

1. **无现有 bridge 实现**: 需从零构建
2. **Session 映射未明确**: bridge 如何映射 OpenClaw session 到 claude_node session
3. **P0 对生产不完整**: Feishu 集成需要 run_id 追踪和 notifier (P1)
4. **Fallback 是降级**: cliBackends fallback 提供 text-only 能力

### 建议

1. **拆分为 P0a + P0b**:
   - P0a: Bridge + models.providers (直接)
   - P0b: Session 映射设计 (需研究)
2. **将 run_id 映射移到 P0**: Feishu 卡片更新必需

---

## 6. 分层架构分析 (06-layered-architecture.md)

**Verdict: PARTIALLY_SOUND** — 架构目标正确，当前实现有问题

### 正确架构 (目标)

```
External Channel (Feishu)
        ↓
   OpenClaw Gateway [adapter only]
        ↓
   models.providers [HTTP custom provider]
        ↓
   openclaw-claude-bridge [薄 bridge 层]
        ↓
   claude-node [Claude runtime]
        ↓
   Claude Code CLI
        ↓
   DB/Control Plane [source of truth]
        ↓
   Feishu Outbound (Notifier)
```

### 当前架构 (生产 - 错误)

```
Feishu → OpenClaw Gateway → cliBackends → wrapper.py → claude_node → Claude CLI
                                              [text-only fallback]
                                              [三合一: 协议+runtime+打包]
```

### 关键问题

1. **cliBackends 作为主路径** — 不应该
2. **wrapper.py 三合一职责** — 违反单一职责原则
3. **models.providers 指向已删除服务** — port 18793 已废弃

---

## 7. 阶段事件通知分析 (07-stage-events.md)

**Verdict: PARTIALLY_SOUND** — 架构上可行，当前路径不可行

### 提议的事件

```typescript
interface StageEvent {
  type: 'stage.started' | 'stage.completed' | 'stage.failed';
  run_id: string;
  stage: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}
```

### 可行性

| 组件 | 可行性 | 风险 |
|------|--------|------|
| 事件 schema | ✅ | 低 |
| run_id → feishu_context DB 映射 | ✅ | 中 (时序) |
| Notifier 轮询 DB | ✅ | 低 |
| 单卡片渐进更新 | ✅ | 中 (Feishu API) |
| 事件顺序保证 | ⚠️ 复杂 | 中 |
| 重连/恢复 | ⚠️ 需设计 | 高 |

### 关键问题

1. **cliBackends 不能支持阶段事件**: 当前生产路径是 text-only fallback
2. **时序竞争**: Bridge 创建 run_id 并存储映射，但必须在 Gateway 返回前完成
3. **Notifier 触发机制未指定**: 轮询 vs 推送 vs 混合

---

## 8. 实施风险分析 (08-risks.md)

**Verdict: PARTIALLY_MITIGATED** — 部分缓解

### 风险矩阵

| 风险 | 可能性 | 影响 | 缓解状态 |
|------|--------|------|----------|
| cliBackends text-only fallback | 高 | 高 | 部分缓解 (P0 规划新主链路) |
| 冷启动延迟高 | 高 | 中 | 未缓解 (daemon-pool 需重写) |
| CLI 参数注入风险 | 中 | 高 | 未缓解 |
| 无 streaming | 高 | 中 | 计划缓解 (models.providers) |
| Session 无持久化 | 中 | 高 | 计划缓解 (P1 DB) |
| daemon-pool 架构错误 | 高 | 高 | 进行中 (归档重写) |

### 缺失缓解

1. **wrapper.py 安全转义**: 未对 CLI 参数做 shell 安全处理
2. **冷启动性能基准**: 未测量当前延迟，无量化目标
3. **Session 持久化**: P1 前无跨重启连续对话能力

---

## 9. 改进方向分析 (09-improvements.md)

**Verdict: PARTIAL** — 需补充

### 未考虑的改进机会

1. **多 Provider Fallback 链**: 当前只有单一 cliBackends fallback
2. **无 Session Pool 的 Bridge**: claude-node 内部处理 session 生命周期
3. **通过 models.providers 的 Streaming**: 完全启用 streaming 支持
4. **健康检查和可观测性**: 无 metrics/日志/跨链路追踪

### 替代方案

**方案 A: Bridge as models.providers (推荐)**
```
OpenClaw Gateway → models.providers → bridge (HTTP) → claude_node → Claude CLI
```
- Bridge 实现 `/v1/chat/completions` (OpenAI-compatible)
- 使用 `api: "openai-completions"` 支持 streaming
- cliBackends 保留作为 fallback
- Session pool 逻辑留在 claude-node 内部

**方案 B: 增强 cliBackends Wrapper**
- 保持 cliBackends 但增强 wrapper.py
- 预热一个或多个 ClaudeController 实例
- 使用 `input: stdin` 模式

**方案 C: 混合**
- cliBackends 用于命令/单次
- models.providers 用于完整对话

---

## 10. 总体评估 (10-overall-assessment.md)

**Overall Verdict: UNSOUND** — 需要修正

### 核心结论

1. **daemon-pool 核心假设错误**: 整个设计依赖 `input: http`，但 OpenClaw 协议根本不支持
2. **Phase 5 任务全部阻塞**: tasks.md 的 5.1、5.2、5.3 依赖不可实现的架构
3. **正确架构清晰**: 三层架构 (Gateway → models.providers → bridge → claude_node) 正确

### 关键修正

| 问题 | 修正 |
|------|------|
| daemon-pool 架构不可能 | 归档 Phase 5，重定向到 bridge + models.providers |
| cliBackends "text-only" 不准确 | 实际上支持 tools/streaming，只是被配置禁用 |
| streaming 被禁用 | 真正问题是输出格式不匹配 (JSONL vs JSON) |

### 建议立即行动

**P0**:
1. 归档 daemon-pool Phase 5 相关任务
2. 实现 bridge 服务 (`/v1/chat/completions`)
3. 更新 models.providers 配置

**P1**:
4. 分离 wrapper.py 职责
5. 启用 streaming 支持
6. 实现 notifier 机制

**P2**:
7. 实现 prewarm 机制解决冷启动
8. 清理废弃配置
9. 评估 MultiAgentRouter

---

## 审查团队

| Agent | 维度 | 任务 |
|-------|------|------|
| 01-routing | COR | OpenClaw 路由解析 |
| 02-capability | SEC/COR | 能力边界 |
| 03-architecture | MNT | 架构设计 |
| 04-daemon-pool | COR | 冲突分析 |
| 05-minimum-change | PRF/MNT | 最小改动方案 |
| 06-layered | MNT | 分层架构 |
| 07-stage-events | COR/PRF | 阶段事件通知 |
| 08-risks | SEC/PRF | 实施风险 |
| 09-improvements | MNT/PRF | 改进方向 |
| 10-overall | ALL | 总体评估 |
