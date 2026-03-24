# Claude-IM

> 将 Claude Code CLI 变为常驻服务，接入飞书（及任意 IM 平台）的完整方案。

## 核心架构

```
飞书用户 ──WebSocket──▶ clawrelay-feishu-server ──SSE──▶ clawrelay-api ──stdin/stdout──▶ Claude Code CLI
                                    │                      │
                              (Python asyncio)        (Go, 端口 50009)
```

**执行内核**：`claude` 完整 CLI（不是 `claude -p`）
- 通过 `--permission-mode bypassPermissions` + `--max-turns 200` 变为 autonomous agent
- 支持工具调用（Bash/文件编辑/Web Search/MCP）
- 会话通过 `--resume` 跨请求恢复

## 目录结构

```
claude-im/
├── README.md              # 本文件
├── ARCHITECTURE.md         # 架构详解
├── QUICKSTART.md           # 快速启动
├── DEPLOYMENT.md           # 部署指南
├── CONFIGURATION.md         # 配置参考
├── MAINTENANCE.md          # 运维指南
├── TROUBLESHOOTING.md      # 故障排查
├── EXTENSION.md            # 扩展指南
├── scripts/
│   ├── start.sh            # 启动全部服务
│   ├── stop.sh             # 停止全部服务
│   └── restart.sh          # 重启全部服务
├── config/
│   └── bots.yaml           # 飞书 bot 配置模板
└── notes/                  # 变更记录 / 设计笔记
```

## 快速启动

```bash
# 1. 克隆本项目
git clone https://github.com/you/claude-im.git ~/claude-im

# 2. 安装 clawrelay-api（Go）
cd ~/claude-im
git clone https://github.com/roodkcab/clawrelay-api.git ../clawrelay-api
cd ../clawrelay-api && go build -o clawrelay-api .

# 3. 安装 clawrelay-feishu-server（Python）
cd ~/claude-im
git clone https://github.com/wxkingstar/clawrelay-feishu-server.git clawrelay-feishu-server
pip install -r clawrelay-feishu-server/requirements.txt

# 4. 配置飞书 bot（修改 App ID/Secret）
cp config/bots.yaml.example config/bots.yaml
vim config/bots.yaml

# 5. 启动
./scripts/start.sh
```

详细步骤见 [QUICKSTART.md](./QUICKSTART.md)

## 组件清单

| 组件 | 仓库 | 技术栈 | 职责 |
|------|------|--------|------|
| **clawrelay-api** | roodkcab/clawrelay-api | Go | OpenAI 兼容 API 网关，spawn Claude CLI |
| **clawrelay-feishu-server** | wxkingstar/clawrelay-feishu-server | Python | 飞书 WebSocket 适配器 |
| **clawrelay-wecom-server** | wxkingstar/clawrelay-wecom-server | Python | 企业微信适配器 |
| **Claude-to-IM** | op7418/Claude-to-IM | TypeScript | Discord/Telegram/Slack/Line 适配层 |
| **Claude Code CLI** | anthropic-ai/claude-code | Node.js | 真正的执行内核 |

## 支持的 IM 平台

| IM 平台 | 适配器 | 开箱即用 | 成熟度 |
|---------|--------|---------|---------|
| **飞书** | clawrelay-feishu-server | ✅ | ⭐⭐⭐⭐⭐ |
| **企业微信** | clawrelay-wecom-server | ✅ | ⭐⭐⭐⭐ |
| **Discord** | Claude-to-IM | ⚠️ 需配置 | ⭐⭐⭐ |
| **Telegram** | Claude-to-IM | ⚠️ 需配置 | ⭐⭐⭐ |
| **Slack** | Claude-to-IM | ⚠️ 需配置 | ⭐⭐⭐ |
| **钉钉** | 无 | ❌ | — |
| **WhatsApp** | 无 | ❌ | — |
| **Microsoft Teams** | 无 | ❌ | — |

详细接入方式见 [EXTENSION.md](./EXTENSION.md)

## 关键特性

- ✅ **零公网 IP**：飞书 SDK WebSocket 长连接
- ✅ **流式回复**：500ms 节流编辑消息
- ✅ **会话持久化**：JSONL 文件存储，`--resume` 恢复
- ✅ **多机器人**：YAML 配置多 bot 实例
- ✅ **多模态**：图片/文件上传分析
- ✅ **工具审批**：bypassPermissions 无需交互

## 飞书开放平台配置

1. 创建企业自建应用
2. 获取 **App ID** + **App Secret**
3. 开通权限：
   - `im:message`
   - `im:message.group_at_msg`
   - `im:resource`
4. 添加事件：`im.message.receive_v1`
5. 启用**长连接**模式
6. 发布应用版本

详见 [DEPLOYMENT.md](./DEPLOYMENT.md)

## 维护

```bash
./scripts/status.sh      # 查看服务状态
./scripts/logs.sh         # 查看实时日志
./scripts/restart.sh      # 重启服务
```

详见 [MAINTENANCE.md](./MAINTENANCE.md)

## 扩展

- 接入其他 IM（Discord/Telegram/企微）
- 自定义命令模块
- 多会话管理策略
- 企业微信适配器：wxkingstar/clawrelay-wecom-server

详见 [EXTENSION.md](./EXTENSION.md)
