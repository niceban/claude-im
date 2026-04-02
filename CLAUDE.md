# Claude-IM 项目认知

## 目标架构（2026-04-02 确认）

```
                    ┌──────────────────────────────────────────────────────┐
                    │                   OpenClaw Gateway                  │
                    │               (Node.js, port 18789)                 │
                    │                                                       │
                    │   飞书 WebSocket ←── Plugin ──→ models.providers  │
                    └──────────────────────┬───────────────────────────────┘
                                           │
                                           │ HTTP (OpenAI-compatible)
                                           ▼
                              ┌────────────────────────────┐
                              │  openclaw-claude-bridge     │
                              │  (新实现, port 18792)      │
                              └─────────────┬──────────────┘
                                            │
                                            ▼
                              ┌────────────────────────────┐
                              │  claude_node (Python)      │
                              │  (/private/tmp/claude-node)│
                              └─────────────┬──────────────┘
                                            │ spawn
                                            ▼
                              ┌────────────────────────────┐
                              │    Claude Code CLI          │
                              │    (v2.1.81+)              │
                              └────────────────────────────┘
```

### 架构要点

| 层级 | 组件 | 职责 |
|------|------|------|
| 面子 | OpenClaw Gateway | 渠道接入、会话管理、外部生态适配 |
| 协议层 | models.providers | HTTP OpenAI-compatible 接口 |
| 转换层 | openclaw-claude-bridge | 协议转换、Session 映射 |
| 核心 | claude-node | Claude Runtime、事件流、Session 控制 |

### 关键结论

1. **cliBackends 是 fallback，不是主路径**：官方定义为 "safety-net rather than a primary path"
2. **CliBackendSchema 不支持 `input: http`**：只有 `arg` 和 `stdin`
3. **正确路径是 models.providers + bridge**：OpenAI-compatible HTTP 接口
4. **Canary 策略**：1% → 10% → 50% → 100% 渐进切换

---

## 当前生产架构（待迁移）

```
                    ┌──────────────────────────────────────────────────────┐
                    │                   OpenClaw Gateway                  │
                    │               (Node.js, port 18789)                 │
                    │                                                       │
                    │   飞书 WebSocket ←── Plugin ──→ cliBackends         │
                    └──────────────────────┬───────────────────────────────┘
                                           │
                                           │ cliBackend (input: arg)
                                           ▼
                              ┌────────────────────────────┐
                              │  claude-node-cli-wrapper.py │
                              │  (/Users/c/ wrapper.py)     │
                              └─────────────┬──────────────┘
                                            │ import
                                            ▼
                              ┌────────────────────────────┐
                              │  claude_node (Python)      │
                              │  (/private/tmp/claude-node)│
                              └─────────────┬──────────────┘
                                            │ spawn
                                            ▼
                              ┌────────────────────────────┐
                              │    Claude Code CLI          │
                              │    (v2.1.81+)              │
                              └────────────────────────────┘
```

### 核心组件

| 组件 | 位置 | 用途 |
|------|------|------|
| OpenClaw Gateway | 进程管理 (launchd) | IM 桥接层，WebSocket 长连接飞书 |
| cliBackends | `~/.openclaw/openclaw.json` | 声明式 CLI 后端配置 |
| wrapper.py | `/Users/c/claude-node-cli-wrapper.py` | Python 封装，CLI Backend 实现 |
| claude_node | `/private/tmp/claude-node` | Claude Code CLI Python 封装 |
| Claude Code CLI | PATH 中 | 真正的 autonomous agent |

### 关键配置

```json
// ~/.openclaw/openclaw.json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "claude-node-cli/claude-sonnet-4-6",
        "fallbacks": ["minimax-cn/MiniMax-M2.7"]
      },
      "cliBackends": {
        "claude-node-cli": {
          "command": "python3",
          "args": ["/Users/c/claude-node-cli-wrapper-v2/wrapper.py"],
          "input": "arg",
          "output": "json",
          "env": {
            "HOME": "/Users/c",
            "PATH": "...",
            "CLAUDE_NODE_PATH": "/private/tmp/claude-node"
          }
        }
      }
    }
  }
}
```

## 已废弃架构

~~clawrelay-feishu-server~~ — 旧版 Python 飞书适配器，通过 HTTP 调用 clawrelay-api，已被 OpenClaw Gateway + CLI Backend 方案替代。

废弃原因：多了一层 HTTP 服务，而 `cliBackends` 配置更简洁且不依赖独立端口。

## 关键修复历史

1. **launchd PATH 隔离问题**：Gateway 由 launchd 启动，PATH 不含用户 shell 环境。必须在 `cliBackends[].env.PATH` 中显式声明完整路径。

2. **input:stdin vs input:arg**：OpenClaw CLI Backend 支持两种模式：
   - `input:stdin`：通过 stdin 传 JSON（插件用）
   - `input:arg`：通过 CLI 参数传 prompt（当前生产方案）
   实际工作的配置是 `input:arg`。

3. **插件 vs cliBackends**：OpenClaw 有两套独立的 CLI 后端声明机制：
   - Plugin: `registerCliBackend()` 注册，需要插件加载
   - cliBackends: `~/.openclaw/openclaw.json` 中直接声明，无需插件
   当前生产方案使用 `cliBackends` 声明，插件代码是死代码。

4. **wrapper.py 路径**：原来硬编码 `/private/tmp/claude-node`，现改为环境变量 `CLAUDE_NODE_PATH`。

5. **streaming 与 Gateway 兼容性问题**：OpenClaw Gateway 的 cliBackends 协议有两种 output 模式：
   - `output: "json"`（当前生产配置）：期望单个完整 JSON 对象。wrapper 输出 JSONL streaming 事件时会 parse 失败，降级为纯文本
   - `output: "jsonl"`：按行分割解析 JSONL，但需要 wrapper 输出格式与 OpenClaw 内置 `stream-json` 格式兼容
   - **当前方案**：`output: "json"` + `CLAUDE_STREAM_EVENTS: "false"` — wrapper 仅输出最终结果 JSON，Gateway 能正确解析
   - 根本原因：自定义 cliBackends 的 JSONL 格式与内置 `claude-cli` backend 的 `stream-json` 格式不同，`parseCliJsonl` 无法正确解析

6. **sessionIdFields 配置**：openclaw.json 的 cliBackends 配置中添加了 `sessionIdFields` 以确保 Gateway 能从 wrapper 结果中提取 session_id

## 项目结构

```
claude-im/
├── CLAUDE.md              # 本文件
├── archive/               # 废弃组件归档
│   └── clawrelay-feishu-server/
├── openspec/              # OpenSpec 变更管理
│   └── changes/archive/   # 已完成变更归档
│       └── 2026-04-02-openclaw-bridge-architecture/  # 正确架构文档
├── openclaw-claude-bridge/  # 新实现：OpenAI-compatible bridge
│   ├── openai_compatible_api/  # Starlette HTTP server
│   ├── claude_node_adapter/     # Protocol conversion + subprocess lifecycle
│   ├── session_mapping/        # LRU session management
│   ├── config/                # Settings + config generator
│   └── tests/                 # 32 tests passing
└── (配置和数据)           # ~/.openclaw/openclaw.json
```

## 归档参考

架构设计文档：`openspec/changes/archive/2026-04-02-openclaw-bridge-architecture/`

包含：
- `ARCHITECTURE.md` — 完整架构设计
- `INDEX.md` — 归档索引
- `CONFLICT.md` — 冲突文档总结
- `daemon-pool-archive/` — daemon-pool 方案归档（基于错误假设）

## 运维命令

```bash
# 重启 Gateway
launchctl kickstart -k gui/$(id -u)/com.openclaw.gateway

# 查看 Gateway 日志
tail -f ~/.openclaw/logs/gateway.log

# 测试 wrapper（旧）
python3 /Users/c/claude-node-cli-wrapper.py "你好"

# 启动 bridge 服务（开发）
cd openclaw-claude-bridge && python main.py

# 启动 bridge 服务（生产）
uvicorn openai_compatible_api.server:app --host 0.0.0.0 --port 18792

# 运行测试
cd openclaw-claude-bridge && python -m pytest tests/ -v
```
