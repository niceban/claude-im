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

### 6.1 环境变量配置链（完整说明）

#### 加载顺序（优先级从高到低）

```
1. os.environ（进程启动时已设置的环境变量）
   ↓
2. .env 文件（通过 main.py 的 load_dotenv() 加载）
   ↓
3. bots.yaml 的 env_vars 字段（兜底）
```

**关键点**：`load_dotenv(override=False)` — 如果 os.environ 已有同名变量，`.env` 文件中的值**不会覆盖**。

#### 必需的环境变量

##### ANTHROPIC_AUTH_TOKEN（Claude Code CLI 认证）

| 属性 | 说明 |
|------|------|
| **来源** | `.env` 文件 或 `os.environ` |
| **用途** | Claude Code CLI 直接 API 调用认证（Agent() tool、多工具组合） |
| **格式** | `sk-cp-ATSzsFW4...`（MiniMax API Token，125字符） |
| **使用组件** | `ClaudeController` subprocess（通过 `{**os.environ}` 继承） |

```bash
# .env 文件
ANTHROPIC_AUTH_TOKEN=sk-cp-ATSzsFW4KgGl7Nlv8bI2ZR4k3CBN_Jpz-E4N2JDrsQCddYsYQms-UsM_xFw9PTuJS0Ps7ieCao-UGTOYVegsccyYPDGlYdulUAYKhbwA1OEc_VYtbULguM0
```

##### ANTHROPIC_BASE_URL

| 属性 | 说明 |
|------|------|
| **来源** | `.env` 文件 或 `os.environ` |
| **用途** | Claude Code CLI 的 API 端点 |
| **格式** | `https://api.minimaxi.com/anthropic` |

##### FEISHU_APP_SECRET（飞书认证）

| 属性 | 说明 |
|------|------|
| **来源** | `os.environ['FEISHU_APP_SECRET']` > `.env` > `bots.yaml` |
| **用途** | 飞书 WebSocket 连接认证 |
| **优先级** | 环境变量 > .env > bots.yaml（环境变量优先，安全） |
| **代码逻辑** | `os.environ.get("FEISHU_APP_SECRET") or bot_data.get("app_secret", "")` |

```bash
# .env 文件
FEISHU_APP_SECRET=woV3uOvc7GBI05CNhjoWGfdfuSUsYk4u
```

##### MINIMAX_API_KEY（MCP 工具认证）

| 属性 | 说明 |
|------|------|
| **来源** | `~/.claude/.claude.json`（MCP server 配置） |
| **用途** | MCP MiniMax 工具（web_search、web_fetch）认证 |
| **格式** | `sk-cp-ATSzsFW4...`（同 ANTHROPIC_AUTH_TOKEN） |
| **使用组件** | `minimax-mcp-js` Node.js MCP server（stdio 模式） |

**注意**：此变量由 Claude Code CLI 启动时通过 `~/.claude/.claude.json` 注入，与 feishu server 进程的 `.env` 无关。

#### .env 文件完整示例

```bash
# 路径: /Users/c/clawrelay-feishu-server/.env
# 加载方式: main.py → load_dotenv(override=False)

# Claude Code CLI 认证（必填）
ANTHROPIC_AUTH_TOKEN=sk-cp-ATSzsFW4KgGl7Nlv8bI2ZR4k3CBN_Jpz-E4N2JDrsQCddYsYQms-UsM_xFw9PTuJS0Ps7ieCao-UGTOYVegsccyYPDGlYdulUAYKhbwA1OEc_VYtbULguM0

# API 端点（必填）
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic

# 飞书 App Secret（优先从环境变量读取，此处兜底）
FEISHU_APP_SECRET=woV3uOvc7GBI05CNhjoWGfdfuSUsYk4u
```

#### launchd 环境变量注意事项

launchd 进程（`com.clawrelay.feishu.plist`）**不继承 shell 环境变量**。

| 变量 | launchd 是否继承 | 说明 |
|------|-----------------|------|
| `ANTHROPIC_AUTH_TOKEN` | ❌ | 需写入 `.env` 文件 |
| `ANTHROPIC_BASE_URL` | ❌ | 需写入 `.env` 文件 |
| `FEISHU_APP_SECRET` | ❌ | 需写入 `.env` 文件 |
| `HOME` | ✅ | plist 中显式设置 |
| `PATH` | ✅ | plist 中显式设置 |
| `http_proxy` 等 | ✅ | plist 中显式清空 |

### 6.2 Bot 配置（`config/bots.yaml`）

```yaml
bots:
  default:
    app_id: "cli_a925d01967791cd5"   # 飞书应用 App ID
    app_secret: "woV3uOvc7GBI05..."  # 兜底：环境变量优先，YAML 其次
    description: "Claude Code Bot"
    model: "MiniMax-M2.7"            # 模型名称
    name: "Claude Bot"
    working_dir: "/Users/c/claude-im" # Claude Code 工作目录
    system_prompt: |
      ## 可用工具
      你可以通过以下 MCP 工具获取实时信息，当用户询问实时内容时**必须**使用：
      - mcp__MiniMax__web_search: 搜索互联网获取最新资讯、新闻、事件
      - mcp__MiniMax__web_fetch: 获取指定 URL 的网页内容
      **使用原则**：
      - 用户问"今天有什么 X"、"最近发生了什么"、"最新消息" → 必须调用 web_search
      - 不要说"我没有实时信息源"，你明明有
    allowed_users: []                # 空=不限制，非空=白名单模式
    env_vars: {}                     # 额外的环境变量（可选）
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
        "MINIMAX_API_KEY": "sk-cp-ATSzsFW4KgGl7Nlv8bI2ZR4k3CBN_Jpz-E4N2JDrsQCddYsYQms-UsM_xFw9PTuJS0Ps7ieCao-UGTOYVegsccyYPDGlYdulUAYKhbwA1OEc_VYtbULguM0",
        "MINIMAX_API_HOST": "https://api.minimaxi.com",
        "MINIMAX_MCP_BASE_PATH": "/Users/c/minimax_outputs/",
        "MINIMAX_RESOURCE_MODE": "local"
      }
    }
  }
}
```

**注意**：`MINIMAX_API_KEY` 在此处的值由 Claude Code CLI 启动时使用，与 `clawrelay-feishu-server/.env` 中的 `ANTHROPIC_AUTH_TOKEN` 是**同一个 token**，但由不同组件在不同时间加载。

### 6.4 环境变量快速检查清单

部署前检查：

```bash
# 1. 检查 .env 文件是否存在
ls -la ~/clawrelay-feishu-server/.env

# 2. 验证 .env 中的 token 与 API key 一致
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/Users/c/clawrelay-feishu-server/.env', override=False)
print('ANTHROPIC_AUTH_TOKEN:', bool(os.environ.get('ANTHROPIC_AUTH_TOKEN')))
print('ANTHROPIC_BASE_URL:', os.environ.get('ANTHROPIC_BASE_URL'))
print('FEISHU_APP_SECRET:', bool(os.environ.get('FEISHU_APP_SECRET')))
"

# 3. 验证 token 有效性
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
