# Implementation Risks Review

## Verdict: PARTIALLY_MITIGATED

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation | Status |
|------|------------|--------|------------|--------|
| cliBackends 是 text-only fallback，toolsdisabled | High | High | 通过 models.providers + bridge 新主链路（P0） | PARTIALLY_MITIGATED |
| 冷启动延迟高（wrapper + claude_node + Claude CLI） | High | Medium | P1 daemon-pool 设计（但需重写） | NOT_MITIGATED |
| CLI 参数注入风险 | Medium | High | prompt 需在 wrapper 层做转义 | NOT_MITIGATED |
| 无 streaming 事件支持 | High | Medium | models.providers 通道支持 streaming | PLANNED_MITIGATION |
| Session 管理无持久化 | Medium | High | DB/Control Plane 设计（P1） | PLANNED_MITIGATION |
| 多层架构延迟叠加 | Medium | Medium | 分层清晰，但需避免过度设计 | ACCEPTED |
| OpenClaw 配置漂移 | Low | Medium | 文档化和归档已有方案 | MITIGATED |
| daemon-pool 设计基于错误假设 | High | High | 归档并重写（新 architecture） | IN_PROGRESS |

## Key Risks

### 1. cliBackends 作为主路径的能力天花板

**当前状态**：生产环境走 `cliBackends` 通道，这是 OpenClaw 的 "safety-net fallback" 路径。

**问题**：
- tools 禁用，无法使用 Claude Code 的完整能力
- 无 streaming 事件
- 无 OpenClaw tools 集成
- 无并行请求处理

**缓解**：ARCHIVE.md 已明确 P0 任务是通过 `models.providers + bridge` 新建主链路，保持 cliBackends 作为 fallback。

**残留风险**：迁移期间双轨并行，配置复杂度增加。

---

### 2. 冷启动延迟（High Impact if unmitigated）

**问题**：`wrapper.py → claude_node → Claude Code CLI` 三层串行冷启动。

**当前缓解**：cliBackends 本身有保底，未规划专项优化。

**缺失缓解**：
- daemon-pool 预热设计（但其架构基于错误假设，需重写）
- 无 session 复用机制

---

### 3. CLI 参数注入风险

**问题**：`input: arg` 模式将 prompt 作为最后一个 CLI 参数传递。如果 prompt 包含特殊字符或恶意构造，可能影响 shell 解析。

**当前缓解**：无明确记录。

**建议缓解**：wrapper.py 需对 prompt 做 shell 安全转义，或切到 `input: stdin` 模式。

---

### 4. Session 状态无持久化

**问题**：claude_node 的 session 管理在内存中，重启后状态丢失。

**缓解**：P1 规划 DB/Control Plane（run_id、stage、artifact 持久化）。

**残留风险**：P1 交付前，无法支持跨重启的连续对话。

---

### 5. daemon-pool 设计需完全重写

**问题**：daemon-pool 设计假设 OpenClaw 支持 `input: http`，但实际 OpenClaw CliBackendSchema 只支持 `arg` 和 `stdin`。

**当前状态**：Phase 5 任务（5.1-5.3）标记为"无法完成"，需通过 `models.providers` 通道重新设计。

**影响**：已投入的 Phase 1-4 设计（session pool 逻辑）可能需要调整接入方式。

---

## Missing Mitigations

1. **wrapper.py 安全转义**：未明确对 CLI 参数做 shell 安全处理
2. **冷启动性能基准**：未测量当前 cold start 延迟，无量化目标
3. **Session 持久化方案**：P1 前无跨重启连续对话能力
4. **双轨并行配置复杂度**：迁移期间维护成本

---

## Issues Found

### Critical

- **daemon-pool 架构错误**：基于 `input: http` 假设，但 OpenClaw 不支持此模式
- **tools 能力受限**：当前主路径无 tools 支持，核心功能退化

### Medium

- **CLI 注入面**：未做 prompt 转义
- **无 session 预热**：每次请求完全冷启动

---

## Recommendation

### 立即行动（P0）

1. **验证双轨配置**：确认 `models.providers` + `cliBackends` 双轨并存可正常工作
2. **实现 bridge 服务**：按 ARCHIVE.md P0 实现 `/v1/chat/completions` 接口
3. **wrapper.py 安全加固**：对 `input: arg` 的 prompt 做 shell 转义

### 短期行动（P1）

1. **Daemon 重设计**：基于 `models.providers` 通道重新设计 session pool
2. **Session 持久化**：设计 DB/Control Plane 方案
3. **冷启动基准**：建立延迟 baseline，指导优化方向

### 风险接受

如短期内无法完成迁移，当前 cliBackends 路径可接受，但需明确：
- 用户体验降级（无 tools、无 streaming）
- 长期维护成本（双轨配置）
