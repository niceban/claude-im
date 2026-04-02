# Overall Assessment

## Executive Summary

本次 OpenClaw + claude-node 集成架构研究揭示了一个**根本性的架构错误**：daemon-pool 设计假设 OpenClaw 支持 `input: http` 模式，但实际 OpenClaw **仅支持 `input: arg` 和 `input: stdin`** 两种模式。这一错误导致 daemon-pool 提案的核心假设不成立，需要完全重构为通过 `models.providers`（HTTP Provider）通道而非 `cliBackends` 通道接入。好消息是，正确架构已经清晰——通过 `models.providers` + 新薄 bridge 层可实现完整功能（tools、streaming、session 复用），且最小改动方案可行。

## Dimension Scores

| Dimension | Score | Summary |
|-----------|-------|---------|
| **COR** | 3/10 | daemon-pool 核心假设（`input: http`）被证伪，Phase 5 任务无法完成 |
| **SEC** | 7/10 | 架构本身无明显安全问题，但 daemon HTTP 服务引入新的攻击面 |
| **PRF** | 6/10 | 热 session 复用可降低延迟至秒级，但当前 daemon-pool 方案无法实现 |
| **MNT** | 5/10 | wrapper.py 三合一职责（协议适配+runtime调用+结果打包）需拆分，但改动范围可控 |

## Overall Verdict: UNSOUND

daemon-pool 提案基于错误假设，其核心机制（通过 `cliBackends` 接入 HTTP daemon）被证伪。虽然 session pool 技术方案完整（LRU 驱逐、异步 init、per-session threading），但接入路径不通。

## Key Strengths

1. **根因定位准确**：研究明确证实 OpenClaw 的 `CliBackendSchema` 只支持 `arg` 和 `stdin`，`input: http` 不存在
2. **正确架构清晰**：三层架构（Gateway → models.providers → bridge → claude_node）正确，分层职责明确
3. **Session Pool 技术成熟**：daemon.py 代码完整，session 复用逻辑经过 clawrelay 生产验证
4. **最小改动方案可行**：保持 cliBackends fallback，新增 models.providers 接入新 bridge，避免大改当前生产配置
5. **冲突文档明确**：daemon-pool 的 proposal.md、design.md、tasks.md 具体冲突位置均已标注

## Key Weaknesses

1. **daemon-pool 核心假设错误**：整个设计依赖 `input: http`，但 OpenClaw 协议根本不支持
2. **Phase 5 任务全部阻塞**：tasks.md 的 5.1、5.2、5.3 依赖不可实现的架构
3. **wrapper.py 职责过多**：协议适配、runtime 调用、结果打包混在一起，缺乏单一职责
4. **streaming 功能未启用**：`CLAUDE_STREAM_EVENTS: false` 禁用了 JSONL streaming，OpenClaw 侧需改 `output: "jsonl"` 才能启用
5. **P0 bridge 服务未实现**：最小改动方案需要新建 bridge 服务，但尚未开始
6. **Daemon HTTP 风险未充分评估**：subprocess 假死检测、进程保活（launchd）等问题存在但未充分解决

## Recommended Actions

### P0（立即执行）
1. **归档 daemon-pool Phase 5 相关任务**：明确标注 `input: http` 方案不可行
2. **实现 bridge 服务**：创建 `/v1/chat/completions` HTTP 接口，内部调用 claude_node
3. **更新 models.providers 配置**：指向新 bridge 服务，保持 cliBackends 作为 fallback

### P1（短期）
4. **分离 wrapper.py 职责**：将协议适配、runtime 调用、结果打包拆分为独立模块
5. **启用 streaming 支持**：评估 `output: "jsonl"` 兼容性，更新 OpenClaw 配置
6. **实现 notifier 机制**：产生阶段事件，支持飞书卡片更新

### P2（中期）
7. **实现 prewarm 机制**：解决冷启动延迟（5-30s）问题，方向 B（stdin 持久化）+ 方向 D（prewarm）组合
8. **清理废弃配置**：归档 clawrelay_bridge 相关配置
9. **评估 MultiAgentRouter**：相比自定义 SessionPool，官方方案可减少维护负担（alpha 风险需权衡）

## Conclusion

daemon-pool 提案的技术实现（session pool、LRU、异步 init）是正确的，但**接入架构根本错误**——试图通过 `cliBackends` 的 `input: http` 模式调用 HTTP daemon，而 OpenClaw 根本不支持此模式。

研究结论**可靠**：
- OpenClaw `CliBackendSchema` 源码已确认，只有 `arg` 和 `stdin` 两种 input 模式
- OpenClaw 官方文档和社区示例均指向 `models.providers` 作为完整功能通道
- daemon-pool design.md 自身已将 "HTTP 模式不兼容" 标注为 Risk，说明设计者已意识到问题

建议**立即停止 daemon-pool 的 Phase 5 工作**，转向最小改动方案：
- 保持当前 cliBackends fallback
- 新增 bridge 服务通过 `models.providers` 接入
- 复用 daemon.py 的 session pool 逻辑（但通过 HTTP bridge 而非 cliBackends 调用）
