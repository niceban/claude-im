# Claude-IM 项目认知

## 当前生产架构

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
          "args": ["/Users/c/claude-node-cli-wrapper.py"],
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

## 项目结构

```
claude-im/
├── CLAUDE.md              # 本文件
├── archive/               # 废弃组件归档
│   └── clawrelay-feishu-server/
├── openspec/              # OpenSpec 变更管理
│   └── changes/archive/   # 已完成变更归档
└── (配置和数据)           # ~/.openclaw/openclaw.json
```

## 运维命令

```bash
# 重启 Gateway
launchctl kickstart -k gui/$(id -u)/com.openclaw.gateway

# 查看 Gateway 日志
tail -f ~/.openclaw/logs/gateway.log

# 测试 wrapper
python3 /Users/c/claude-node-cli-wrapper.py "你好"
```
