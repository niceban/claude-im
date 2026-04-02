## Why

当前生产架构将 cliBackends 作为主执行路径，但 cliBackends 官方定义为 "safety-net rather than a primary path"，且 Schema 只支持 `input: arg/stdin`，不支持 HTTP 模式。这导致：
1. 阶段事件不可见（deliver() 只在 final 触发）
2. 能力受限（streaming 被禁用）
3. wrapper.py 三合一职责（协议适配+runtime调用+结果打包）

需要迁移到正确的 `models.providers + bridge` 架构，实现 OpenClaw 面子和 claude-node 里子的最大化能力发挥。

## What Changes

- 新增 `openclaw-claude-bridge` 服务作为 OpenAI-compatible HTTP 接口
- 配置 `models.providers` 指向新的 bridge 服务
- 100% 流量切换到 bridge（默认），不做灰度
- cliBackends 降级为 fallback（可选废弃）
- TDD 开发流程：每个模块独立测试通过后再进入下一模块

## Capabilities

### New Capabilities

- `openai-compatible-api`: 实现 `/v1/chat/completions`、`/v1/models`、`/health` 接口
- `claude-node-adapter`: 桥接 HTTP 请求与 claude-node ClaudeController
- `session-mapping`: 管理 conversation_id → session_id 映射
- `models-provider-config`: OpenClaw models.providers 配置管理
- `tdd-test-suite`: 每个模块的单元测试和集成测试

### Modified Capabilities

- 无（当前 cliBackends 配置保留作为 fallback，不删除）

## Impact

- 新增服务：`openclaw-claude-bridge`（端口 18792）
- 配置文件：`~/.openclaw/openclaw.json` 更新 models.providers
- 废弃：daemon-pool 方案（基于错误假设 `input: http`）
- 测试：TDD 流程，每个模块独立测试
