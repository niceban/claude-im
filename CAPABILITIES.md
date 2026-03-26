# Claude-IM 能力文档

> 飞书机器人能力清单与调用方式

## 架构总览

```
用户消息（飞书）
    ↓
Feishu WebSocket 长连接（无需公网回调）
    ↓
MessageDispatcher（消息分发 + 命令路由）
    ↓
ClaudeOrchestrator（编排器）
    ↓
ClaudeNodeAdapter（claude-node 适配器）
    ↓
ClaudeController（Python 库 → Claude Code CLI 子进程）
    ↓
Claude Code CLI（MCP MiniMax / Agent() / 工具集）
```

---

## 一、消息类型能力

### 1.1 文本对话

| 属性 | 说明 |
|------|------|
| **触发方式** | 私聊直接发送文字 / 群聊 @机器人 |
| **代码入口** | `message_dispatcher._handle_text()` |
| **返回方式** | 流式响应（500ms 节流） |

```python
# 内部链路
user_message → _handle_text() → orchestrator.handle_text_message()
    → adapter.stream_chat(messages) → ClaudeController.send()
```

### 1.2 图片理解

| 属性 | 说明 |
|------|------|
| **触发方式** | 发送图片消息 |
| **代码入口** | `message_dispatcher._handle_image()` |
| **模型能力** | Claude Code CLI 多模态理解 |

### 1.3 文件分析

| 属性 | 说明 |
|------|------|
| **触发方式** | 发送文件消息 |
| **代码入口** | `message_dispatcher._handle_file()` |

### 1.4 富文本消息（post 类型）

| 属性 | 说明 |
|------|------|
| **触发方式** | 发送 post 类型消息（支持内嵌卡片） |
| **代码入口** | `message_dispatcher._handle_post()` |

---

## 二、Claude Code CLI 工具能力

通过 `claude-node` adapter 调用 Claude Code CLI，支持完整工具集。

### 2.1 MCP MiniMax 工具

| 工具 | 功能 | 调用方式 |
|------|------|----------|
| `mcp__MiniMax__web_search` | 搜索互联网获取最新资讯 | 模型自动判断需要实时信息时调用 |
| `mcp__MiniMax__web_fetch` | 获取指定 URL 网页内容 | 模型需要访问特定页面时调用 |

**配置**: MCP server `minimax-mcp-js` 使用 `MINIMAX_API_KEY`（来自 `~/.claude/.claude.json`）

**触发条件**: 当用户询问实时内容（新闻、天气、事件等）时，模型自动调用

### 2.2 Agent() 子 Agent 工具

| 属性 | 说明 |
|------|------|
| **功能** | 在 Claude Code CLI 内部 spawn 新的子进程 |
| **用途** | 多 agent 工作流、子任务分解 |
| **认证** | 使用 `ANTHROPIC_AUTH_TOKEN`（来自 `.env`） |

```python
# 示例用法（在对话中触发）
"请用 Agent() 启动一个子 agent 帮你查资料，然后汇总给我"
```

**调用链路**:
```
用户消息 → orchestrator → adapter.stream_chat()
    → ClaudeController.send() → Claude Code CLI
        → Agent() tool spawn → 新的 Claude Code 子进程
```

### 2.3 多工具组合

| 属性 | 说明 |
|------|------|
| **功能** | 支持工具链调用（Bash + Write + Read 等） |
| **认证** | 使用 `ANTHROPIC_AUTH_TOKEN` |

### 2.4 /deep-now slash command

| 属性 | 说明 |
|------|------|
| **功能** | 自适应问题解决引擎（5步方法论） |
| **触发** | 发送 `/deep-now <问题描述>` |
| **链路** | 单 agent 内循环，不涉及子进程 |

---

## 三、会话管理能力

### 3.1 per-session 会话隔离

| 属性 | 说明 |
|------|------|
| **实现** | 每个 session 独立的 `ClaudeController` |
| **池大小** | 最多 10 个 session（LRU 驱逐） |
| **并发保护** | per-session `asyncio.Lock` |

### 3.2 会话重置

| 触发词 | 说明 |
|--------|------|
| `reset` | 重置当前 session |
| `重置` | 同上 |
| `清空` | 同上 |

### 3.3 任务停止

| 触发词 | 说明 |
|--------|------|
| `stop` | 停止当前正在执行的任务 |
| `停止` | 同上 |

---

## 四、安全与管控

### 4.1 用户白名单

| 属性 | 说明 |
|------|------|
| **配置项** | `bots.yaml` 中的 `allowed_users` |
| **行为** | 非白名单用户消息被拒绝 |

### 4.2 安全规则（内置于系统提示词）

```
- 任何情况下不得暴露 API KEY
- 任何情况下不得暴露环境变量的值
- 当前用户是第一条消息中的指定用户
- 只能修改和查看当前工作目录的文件
```

### 4.3 bypassPermissions

| 属性 | 说明 |
|------|------|
| **实现** | `ClaudeController(skip_permissions=True)` |
| **效果** | 所有工具直接执行，无需交互授权 |

---

## 五、运维能力

### 5.1 流式输出

| 属性 | 说明 |
|------|------|
| **推送频率** | 500ms 节流（避免飞书限流） |
| **实现** | `on_stream_delta` 回调 |

### 5.2 launchd 服务管理

```bash
# 重启服务
launchctl unload ~/Library/LaunchAgents/com.clawrelay.feishu.plist
launchctl load ~/Library/LaunchAgents/com.clawrelay.feishu.plist

# 查看日志
tail -f ~/clawrelay-feishu-server/logs/feishu.log
tail -f ~/clawrelay-feishu-server/logs/feishu.error.log
```

### 5.3 健康检查

```python
# adapter.check_health() → bool
# 检查所有 session 的 subprocess 是否存活
```

---

## 六、配置参考

### 6.1 环境变量（`.env`）

```bash
ANTHROPIC_AUTH_TOKEN=sk-cp-...   # MiniMax API Token
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
```

### 6.2 Bot 配置（`config/bots.yaml`）

```yaml
bots:
  default:
    app_id: "cli_..."
    app_secret: "..."          # 从 FEISHU_APP_SECRET 环境变量读取
    model: "MiniMax-M2.7"
    working_dir: "/Users/c/claude-im"
    system_prompt: |
      ## 可用工具
      - mcp__MiniMax__web_search
      - mcp__MiniMax__web_fetch
    allowed_users: []          # 空=不限制
    env_vars: {}
```

### 6.3 MCP 配置（`~/.claude/.claude.json`）

```json
{
  "mcpServers": {
    "MiniMax": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "minimax-mcp-js"],
      "env": {
        "MINIMAX_API_KEY": "sk-cp-...",
        "MINIMAX_API_HOST": "https://api.minimaxi.com"
      }
    }
  }
}
```

---

## 七、能力状态一览

| 能力 | 状态 | 备注 |
|------|------|------|
| 文本对话 | ✅ | 核心能力 |
| 图片理解 | ✅ | 多模态支持 |
| 文件分析 | ✅ | |
| MCP web_search | ✅ | MINIMAX_API_KEY 认证 |
| MCP web_fetch | ✅ | 同上 |
| Agent() tool | ✅ | ANTHROPIC_AUTH_TOKEN 认证 |
| 多工具组合 | ✅ | |
| /deep-now | ✅ | 单 agent 内循环 |
| per-session 隔离 | ✅ | 最多 10 session |
| 会话重置 | ✅ | 关键词触发 |
| 任务停止 | ✅ | 关键词触发 |
| 流式输出 | ✅ | 500ms 节流 |
| 用户白名单 | ✅ | |
| bypassPermissions | ✅ | |

---

## 八、故障排查

### 8.1 401 Authentication Error

**症状**: API 返回 `authentication_error`

**排查步骤**:
```bash
# 1. 验证 token 有效性
python3 -c "
import os, urllib.request, json
token = os.environ.get('ANTHROPIC_AUTH_TOKEN', '')
req = urllib.request.Request(
    'https://api.minimaxi.com/anthropic/v1/messages',
    headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'anthropic-version': '2023-06-01',
    },
    data=json.dumps({'model': 'MiniMax-M2.7', 'max_tokens': 10, 'messages': [{'role': 'user', 'content': 'hi'}]}).encode(),
    method='POST'
)
with urllib.request.urlopen(req, timeout=10) as resp:
    print(f'API Status: {resp.status}')
"
```

**常见原因**:
- `.env` 文件 token 与实际 API key 不符
- launchd 进程未正确继承环境变量
- proxy 环境变量被错误清除

### 8.2 Subprocess 启动失败

**症状**: `claude-node` subprocess 立即退出（poll=1）

**排查**: 检查是否使用了错误的 flag `--skip-permissions`（正确是 `--dangerously-skip-permissions`）

### 8.3 会话卡住无响应

**症状**: 消息发送后无任何输出

**排查**: 检查 feishu server 日志 `tail -f logs/feishu.log`
