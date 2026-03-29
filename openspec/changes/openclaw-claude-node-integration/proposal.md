## Why

当前 `clawrelay-feishu-server` 架构复杂难维护：Feishu 消息通道、claude-node 桥接、SessionManager 多层耦合。OpenClaw 原生提供 24+ 消息通道和 Gateway WebSocket 协议，但 AI 引擎绑定在 Provider。通过 OpenClaw Provider 插件机制，将 claude-node（发挥 Claude CLI 本地子进程管理能力）作为 AI 引擎接入，可实现：

- OpenClaw 做通讯层（消息路由、通道管理）
- claude-node 做 AI 处理层（Claude CLI subprocess、Session 管理）
- 架构简洁，双方能力最大化利用

## What Changes

1. **新建 `clawrelay-bridge/`** - Python Bridge Server，作为 claude-node 的 OpenAI-compatible HTTP API wrapper
2. **OpenClaw Provider 配置** - 在 `openclaw.json` 中配置 claude-node Bridge 为自定义 Provider
3. **Session 管理** - 复用 session_mapping 表实现 OpenClaw session ↔ claude-node session 的 1:1 映射
4. **Fallback 机制** - 健康检查 + OpenClaw 上线维修（claude-node 宕机时 OpenClaw 激活，修复后立即下线）
5. **归档历史代码** - `clawrelay-feishu-server/`、`clawrelay-report/` 归档为历史代码

## Capabilities

### New Capabilities

- `openclaw-provider`: OpenClaw Provider 插件配置，将 claude-node Bridge 注册为 AI Provider
- `claude-node-bridge`: claude-node HTTP API Wrapper，封装 claude-node 为 OpenAI-compatible HTTP 服务
- `health-monitor`: 健康检查组件，检测 claude-node 存活状态，触发 Fallback
- `session-mapper`: 会话映射表，管理 OpenClaw session ↔ claude-node session 的对应关系
- `fallback-manager`: Fallback 管理器，协调 OpenClaw 与 claude-node 的故障切换

### Modified Capabilities

<!-- 暂无 - 本次为全新实现 -->

## Impact

- **新增目录**: `clawrelay-bridge/` - Bridge Server 实现
- **配置文件**: `openclaw.json` - Provider 配置变更
- **归档目录**: `clawrelay-feishu-server/`、`clawrelay-report/` - 历史代码归档
- **依赖**: OpenClaw 运行在 `ws://127.0.0.1:18789`，claude-node (Python 包)
