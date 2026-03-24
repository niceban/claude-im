# Claude-IM 项目认知

> 本文件定义 claude-im 项目的技术决策、约束和开发规范。

## 技术栈

```
IM 适配层：  clawrelay-feishu-server (Python)  # 飞书 WebSocket 长连接
IM 适配层：  clawrelay-wecom-server (Python)    # 企业微信
IM 适配层：  Claude-to-IM (TypeScript)          # Discord/Telegram/Slack/Line
API 网关：   clawrelay-api (Go)                # spawn claude CLI，OpenAI 兼容 HTTP 接口
进程封装：   claude-node (Python)              # spawn claude CLI，Python 库（可直接嵌入）
执行内核：   Claude Code CLI (v2.1.81)           # 真正的 autonomous agent
```

## 核心架构：两种等价的 Claude CLI 封装

**claude-node 和 clawrelay-api 做的是同一件事**，只是语言和接口形式不同：

```
                              ┌─────────────────────────────────┐
                              │      Claude Code CLI            │
                              │  (真正的 autonomous agent)       │
                              │  --permission-mode bypassPerms  │
                              └──────────────┬──────────────────┘
                                             │ stdin/stdout (stream-json)
                    �────────────────────────┼────────────────────────┐
                                            │                        │
                        ┌───────────────────▼──────────┐    ┌──────▼──────────┐
                        │  claude-node (Python 库)      │    │ clawrelay-api   │
                        │  spawn claude 子进程          │    │ (Go HTTP 服务)   │
                        │  Python 直接调用               │    │  :50009         │
                        │  ClaudeController            │    │  /v1/chat/completions
                        │  MultiAgentRouter            │    │  SSE streaming  │
                        └──────────────────────────────┘    └──────┬──────────┘
                                                                     │
                                                           ┌─────────▼──────────┐
                                                           │  feishu-server     │
                                                           │  (HTTP 调 API)    │
                                                           └───────────────────┘
```

### 详细对比

| | `claude-node` | `clawrelay-api` |
|--|---|---|
| **语言** | Python | Go |
| **接口形式** | Python 库（直接 import） | HTTP REST API |
| **是否需要 HTTP 服务** | ❌ 不需要 | ✅ 需要（端口 50009） |
| **多会话路由** | `MultiAgentRouter` 内置 | 需额外部署多实例 |
| **session 持久化** | 应用层实现 | JSONL 文件内置 |
| **WebSocket 查看器** | ❌ 无 | ✅ 有（`:50009/session/{id}`） |
| **OpenAI 兼容** | ❌ 无 | ✅ `/v1/chat/completions` |
| **适合场景** | Python 项目嵌入、定制开发 | 多语言客户端接入 |
| **工具调用支持** | ✅ 完整 | ✅ 完整 |
| **会话分叉** | ✅ `fork()` | 需手动 `--resume` |

### 为什么当前用 clawrelay-api 而不是 claude-node？

feishu-server 是 Python，可以用 `claude-node` 直接 import，不需要 HTTP 调用。但 `clawrelay-api` 提供了：
- OpenAI 兼容接口（通用性更强）
- 内置 session 持久化
- WebSocket 调试查看器
- 多语言通用性（任何能发 HTTP 的语言都能接入）

**可以替换**：如果想用 `claude-node` 替代 `clawrelay-api`，直接 `pip install claude-node`，把 feishu-server 中对 `http://localhost:50009` 的调用替换为 `ClaudeController` 的 Python import 调用。

## 架构约束

1. **IM 适配层必须通过 WebSocket 长连接** — 无需公网 IP/回调 URL
2. **bypassPermissions 模式** — 非交互执行，所有工具直接跑；生产必须配 `allowed_users` 白名单
3. **会话通过 `--resume`** — JSONL 文件持久化，kill 进程不丢会话
4. **500ms 节流** — 推送消息频率，避免飞书限流
5. **OpenAI 兼容接口** — clawrelay-api 的 `/v1/chat/completions` 可被任意 OpenAI 客户端调用

## 项目结构规范

```
claude-im/
├── scripts/          # 运维脚本（启动/停止/日志/状态）
├── config/           # 配置模板（bots.yaml.example）
├── notes/            # 变更记录 / 设计笔记
└── (外部依赖 clone 到 ~/ 目录)
    ~/clawrelay-api              # Go API 网关
    ~/clawrelay-feishu-server    # 飞书适配器
    ~/clawrelay-wecom-server     # 企业微信适配器
    ~/claude-node/               # Python CLI 封装库（可选替换 clawrelay-api）
```

## 决策记录

### 选型决策

- **用 CLI 而非 HTTP API**：Claude Code CLI 有完整工具能力（Bash/文件/MCP），纯 HTTP API 没有
- **选 clawrelay-api 而非 claude-node（当前）**：HTTP 接口通用性更强，session 持久化开箱即用
- **备选 claude-node**：适合纯 Python 嵌入、需要精细控制多 agent 路由的场景

### 禁止事项

- 禁止在 `allowed_users` 为空时对公网暴露 clawrelay-api（bypassPermissions 风险）
- 禁止不配置 `max-turns` 上线（无限循环风险）
- 禁止把会话目录放在网络文件系统上（JSONL 写入依赖本地磁盘）

## 开发规范

### 两种接入方式的权衡

**方式 A — HTTP 调用 clawrelay-api（当前）**：
```python
# feishu-server 中的 claude_relay_adapter.py
async with aiohttp.ClientSession() as sess:
    async with sess.post("http://localhost:50009/v1/chat/completions",
                         json={"model": "vllm/sonnet", "messages": [...], "stream": True}) as r:
        async for line in r.content:
            # 解析 SSE
```
✅ 部署简单，Go 服务独立运行
❌ 需要多一个网络跳

**方式 B — 直接 import claude-node（更 Pythonic）**：
```python
from claude_node import ClaudeController

ctrl = ClaudeController(skip_permissions=True, resume=session_id)
ctrl.start()
result = ctrl.send("用户消息", timeout=120)
ctrl.stop()  # 或用 context manager
```
✅ 无网络开销，更精细控制多 agent
❌ 需要自己实现 HTTP API 层的 session 持久化

### 新增 IM 适配器

1. 优先找现成仓库（clawrelay-wecom-server 模式）
2. 参考 clawrelay-feishu-server 的接口设计（`src/adapters/`、`src/transport/`）
3. 遵循相同的 `relay_url` 配置约定

## 运维边界

- **日志**：`~/claude-im/logs/` + 各组件子目录
- **会话**：`~/clawrelay-api/sessions/` JSONL 文件
- **聊天记录**：`~/clawrelay-feishu-server/logs/chat.jsonl`
- **升级顺序**：先升级 clawrelay-api，再升级 feishu-server，最后测试
