# 扩展指南

## 接入其他 IM 平台

### IM 平台成熟度矩阵

| IM 平台 | 适配器 | 成熟度 | 开箱即用 | 接入难度 |
|---------|--------|--------|---------|---------|
| **飞书** | clawrelay-feishu-server | ⭐⭐⭐⭐⭐ | ✅ | 1/5 |
| **企业微信** | clawrelay-wecom-server | ⭐⭐⭐⭐ | ✅ | 1/5 |
| **Discord** | Claude-to-IM | ⭐⭐⭐ | ⚠️ 需配置 | 2/5 |
| **Telegram** | Claude-to-IM | ⭐⭐⭐ | ⚠️ 需配置 | 2/5 |
| **Slack** | Claude-to-IM | ⭐⭐⭐ | ⚠️ 需配置 | 2/5 |
| **Line** | Claude-to-IM | ⭐⭐ | ⚠️ 需配置 | 3/5 |
| **钉钉** | 无现成方案 | — | ❌ | 4/5 |
| **WhatsApp** | 无现成方案 | — | ❌ | 5/5 |
| **Microsoft Teams** | 无现成方案 | — | ❌ | 4/5 |

### 企业微信（开箱即用 ✅）

项目：[wxkingstar/clawrelay-wecom-server](https://github.com/wxkingstar/clawrelay-wecom-server)

架构与 feishu-server 完全一致，配置方式相同。

```bash
git clone https://github.com/wxkingstar/clawrelay-wecom-server.git ~/clawrelay-wecom-server
cd ~/clawrelay-wecom-server
pip install -r requirements.txt

# 配置
cp config/bots.yaml.example config/bots.yaml
vim config/bots.yaml

# 启动
python3 main.py
```

架构与 feishu-server 完全一致，只是适配的 IM API 不同。

### Discord / Telegram / Slack / Line（Claude-to-IM）

项目：[op7418/Claude-to-IM](https://github.com/op7418/Claude-to-IM)（1488 stars）

一套 TypeScript 代码，同时支持 Discord、Telegram、Slack、Line。

```bash
git clone https://github.com/op7418/Claude-to-IM.git ~/Claude-to-IM
cd ~/Claude-to-IM
npm install
```

**架构**：

```
IM Platform (Discord/Telegram/Slack/Line)
        │
        ▼
   +-----------+
   |  Adapter  │  ← 平台消息 → 统一消息格式
   +-----------+
        │
        ▼ Bridge Manager ← LLMProvider（注入 claude-node / clawrelay-api）
        │
        ▼ Host Application ← 你需要实现的存储/调用层
```

**接入步骤**：

1. 实现 `LLMProvider` 接口（调用 claude-node 或 clawrelay-api）
2. 实现 `BridgeStore`（~30 个存储方法）
3. 配置各平台 Bot Token
4. 启动服务

**注意**：Claude-to-IM 默认使用 `claude-node`（Claude HTTP API），工具调用能力有限。如需完整工具能力，可将 `LLMProvider` 替换为对 clawrelay-api 的调用。

### 钉钉（需自研）

钉钉开放平台有 [Go SDK](https://github.com/open-dingtalk/dingtalk) 和 [Java SDK](https://github.com/teambition/dingtalk-sdk)，但无现成 Claude 集成方案。

**接入难点**：
- 钉钉 Bot 消息签名验证复杂
- 官方推荐网关模式（需要公网回调 URL），长连接需要 WebSocket 模式
- SDK 文档分散

**建议路径**：参考 clawrelay-feishu-server 的架构，为钉钉重新实现一套适配层。

### Telegram

同上，参考 `Claude-to-IM` 库的 Adapter 接口实现。

## 自定义命令开发

在 `src/handlers/custom/` 下创建模块：

### 示例：天气命令

```python
# src/handlers/custom/weather.py
import urllib.request
import json
from src.handlers.command_handlers import CommandHandler

class WeatherCommandHandler(CommandHandler):
    command = "weather"
    description = "查询天气：weather 北京"

    def handle(self, cmd, stream_id, user_id):
        city = cmd[len("weather "):].strip()
        if not city:
            return "用法: weather <城市名>", None

        try:
            # 调天气 API（示例）
            url = f"https://api.example.com/weather?city={city}"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            return f"{city}天气：{data['temp']}°C, {data['desc']}", None
        except Exception as e:
            return f"查询失败: {e}", None

def register_commands(command_router):
    command_router.register(WeatherCommandHandler())
```

### 示例：文件搜索命令

```python
# src/handlers/custom/find.py
import os
import fnmatch
from src.handlers.command_handlers import CommandHandler

class FindCommandHandler(CommandHandler):
    command = "find"
    description = "在 working_dir 搜索文件：find *.py"

    def handle(self, cmd, stream_id, user_id):
        # cmd = "find *.md"
        pattern = cmd[len("find "):].strip()
        if not pattern:
            return "用法: find <pattern>", None

        # 默认搜索 /tmp 或可配置目录
        results = []
        for root, dirs, files in os.walk("/tmp"):
            for name in files:
                if fnmatch.fnmatch(name, pattern):
                    results.append(os.path.join(root, name))

        if results:
            return "\n".join(results[:20]), None  # 最多返回 20 个
        else:
            return "未找到匹配文件", None

def register_commands(command_router):
    command_router.register(FindCommandHandler())
```

## 修改流式行为

### 调整节流延迟

```python
# src/transport/message_dispatcher.py
async def dispatch_stream(self, stream_id, content):
    # 当前每 0.5 秒推送一次
    await asyncio.sleep(0.5)
    # 调高到 1.0 秒减少限流
```

### 修改消息格式

```python
# src/adapters/feishu_api.py
async def edit_message(self, message_id, content):
    # 当前发送纯文本
    # 可以改为发送富文本（post）格式
```

## 多机器人配置

```yaml
bots:
  # 助手机器人
  assistant:
    app_id: "cli_xxx"
    app_secret: "xxx"
    relay_url: "http://localhost:50009"
    model: "vllm/claude-sonnet-4-6"
    name: "Claude 助手"
    system_prompt: "你是一个专业助手"

  # 编程机器人
  coder:
    app_id: "cli_yyy"
    app_secret: "yyy"
    relay_url: "http://localhost:50009"
    model: "vllm/claude-opus-4-6"
    name: "Claude 编程助手"
    working_dir: "/path/to/code"
    system_prompt: "你是一个编程专家，专注于代码优化和bug修复"
```

## 会话持久化增强

### 外置会话存储

修改 `clawrelay-feishu-server` 的 SessionManager，支持 MySQL/Redis：

```python
# src/core/session_manager.py
class PersistentSessionManager:
    def __init__(self, redis_url):
        import redis
        self.redis = redis.from_url(redis_url)

    def save(self, session_id, messages):
        self.redis.set(f"session:{session_id}",
                       json.dumps(messages), ex=86400*7)

    def load(self, session_id):
        data = self.redis.get(f"session:{session_id}")
        return json.loads(data) if data else []
```

### 会话压缩（防止上下文溢出）

当会话超过 N 条消息时，自动压缩：

```python
async def compress_session(self, session_id):
    """将旧消息摘要化，保留最近 N 条"""
    messages = self.load(session_id)
    if len(messages) > 50:
        summary_prompt = "请简要总结以下对话的核心内容：\n" + \
                         "\n".join([m['content'] for m in messages])
        # 调用 claude 总结
        summary = await call_claude(summary_prompt)
        # 保留系统+总结+最近消息
        compressed = [messages[0], {'role': 'assistant', 'content': summary}] + \
                     messages[-20:]
        self.save(session_id, compressed)
```

## 接入 MCP (Model Context Protocol)

Claude Code 支持 MCP 工具。在 clawrelay-api 中注入：

```yaml
# bots.yaml
bots:
  default:
    env_vars:
      # MCP 服务器
      CLAUDECODE_MCP_SERVERS: "/path/to/mcp-server"
```

或在 claude CLI 层面配置 MCP。

## 负载均衡（多实例）

当单台机器无法承载时：

```
                    ┌──▶ clawrelay-api :50091
                    │
飞书 ──▶ feishu ───┼──▶ clawrelay-api :50092
(server)            │
  (Python           │
   支持多           └──▶ clawrelay-api :50093
   relay_url)
```

```yaml
# feishu-server 随机选择
bots:
  default:
    relay_url: "http://localhost:50091"
    # 或使用 nginx 负载均衡
    # relay_url: "http://lb/clawrelay"
```

## Webhook 集成

当需要将 AI 响应推送到其他系统时：

```python
# src/core/claude_relay_orchestrator.py
async def on_response_complete(self, session_id, response):
    # 响应完成后回调
    if webhook_url := os.getenv("WEBHOOK_URL"):
        import httpx
        await httpx.AsyncClient().post(webhook_url, json={
            "session_id": session_id,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
```

## 多语言支持

在 feishu-server 中检测用户语言：

```python
# src/transport/message_dispatcher.py
async def detect_language(self, text):
    # 简单检测：是否包含中文字符
    if any('\u4e00' <= c <= '\u9fff' for c in text):
        return "zh"
    return "en"
```

然后在 `system_prompt` 中注入语言指令。

---

## 用 claude-node 替代 clawrelay-api

claude-node（claw-army/claude-node）和 clawrelay-api 做的是**完全相同的事**：驱动 `claude` CLI 子进程。

**用 claude-node 替换 clawrelay-api 的优势：**
- Python 直接 import，无需 HTTP 网络开销
- `MultiAgentRouter` 内置多会话路由，开箱即用
- 更精细的 `on_message` 回调控制
- 每个 `ClaudeController` 是独立进程，更好的隔离

**替换步骤：**

1. 安装：
```bash
pip install claude-node
```

2. 在 feishu-server 中替换调用方式：

```python
# 旧方式（HTTP 调用 clawrelay-api）：
async def call_claude(self, prompt):
    async with self.session.post(f"{self.relay_url}/v1/chat/completions",
                                  json={"messages": [...], "stream": True}) as r:
        async for line in r.content:
            yield line

# 新方式（直接 import claude-node）：
from claude_node import ClaudeController

class ClaudeNodeAdapter:
    def __init__(self, session_id=None, system_prompt=""):
        self.ctrl = ClaudeController(
            skip_permissions=True,
            resume=session_id,
            system_prompt=system_prompt,
        )

    def start(self):
        self.ctrl.start()

    def send(self, message, timeout=120):
        result = self.ctrl.send(message, timeout=timeout)
        return result.result_text if result else None

    def stop(self):
        self.ctrl.stop()
```

**多 Agent 路由示例**（claude-node 独有）：

```python
from claude_node import MultiAgentRouter, AgentNode

with MultiAgentRouter() as router:
    router.add(AgentNode("PM", system_prompt="你是产品经理"))
    router.add(AgentNode("DEV", system_prompt="你是工程师"))
    router.start_all()

    # 发给 PM
    pm_reply = router.send("PM", "设计一个用户登录功能")

    # PM 的回复转发给 DEV 评审
    dev_reply = router.route(pm_reply or "", to="DEV",
                             wrap="PM 的方案如下，请评审：\n{message}")
```

