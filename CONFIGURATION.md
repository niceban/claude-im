# 配置参考

## bots.yaml 完整配置

```yaml
bots:
  # 机器人实例名称（可配置多个）
  default:
    # === 必填 ===
    app_id: "cli_a925d01967791cd5"       # 飞书 App ID
    app_secret: "woV3uOvc7GBI05CNhjo..." # 飞书 App Secret
    relay_url: "http://localhost:50009"   # clawrelay-api 地址

    # === 可选 ===
    name: "Claude Bot"                    # 机器人名称（群聊中过滤 @提及）
    description: "Claude Code Bot"        # 机器人描述
    model: "vllm/claude-sonnet-4-6"     # 模型（见模型映射）
    working_dir: ""                        # Claude 工作目录（留空用默认 sessions/）
    system_prompt: ""                     # 系统提示词
    max_turns: 200                         # 最大工具调用轮次（默认 200）

    # 用户白名单（留空 = 不限制）
    allowed_users:
      - "ou_xxxxxxxxxxxx"

    # 注入环境变量（会传给 claude 子进程）
    env_vars:
      ANTHROPIC_API_KEY: "sk-ant-..."
      # 自定义变量也可以
      # MY_CUSTOM_VAR: "value"

    # 自定义命令模块
    custom_commands:
      - "src.handlers.custom.demo_commands"
```

## 模型映射

clawrelay-api 内部将 `vllm/` 前缀的模型名映射为真实 Claude 模型：

| 配置值 | 实际模型 |
|--------|---------|
| `vllm/claude-sonnet-4-6` | Claude Sonnet 4 |
| `vllm/claude-opus-4-6` | Claude Opus 4 |
| `vllm/claude-haiku-4-5-20251001` | Claude Haiku 4 |
| `gpt-4` | → Opus |
| `gpt-4o` / `gpt-4-turbo` | → Sonnet |
| `gpt-3.5-turbo` / `gpt-4o-mini` | → Haiku |

## 环境变量

### clawrelay-api 运行时

| 变量 | 说明 |
|------|------|
| `HTTP_PROXY` / `HTTPS_PROXY` | 代理（如果需要） |
| `ANTHROPIC_API_KEY` | Claude API Key（通过 env_vars 也可注入） |
| `ANTHROPIC_BASE_URL` | API 端点（默认官方） |

### feishu-server 运行时

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BOT_CONFIG_PATH` | `config/bots.yaml` | 配置文件路径 |
| `CHAT_LOG_DIR` | `logs` | 聊天日志目录 |

## clawrelay-api 会话存储

```
~/clawrelay-api/sessions/
├── feishu:ou_xxxxx:default.jsonl    # 飞书用户会话
├── feishu:ou_yyyyy:default.jsonl
└── ...
```

每个会话为 JSONL 文件，每行一个事件：

```jsonl
{"type":"request","time":"2026-03-24T14:00:00Z","messages":[...]}
{"type":"delta","time":"2026-03-24T14:00:01Z","content":"Hello"}
{"type":"tool_use","time":"2026-03-24T14:00:02Z","name":"Bash","input":{...}}
{"type":"completion","time":"2026-03-24T14:00:05Z","text":"..."}
```

## 自定义命令模块

在 `src/handlers/custom/` 下创建 Python 文件：

```python
# src/handlers/custom/demo_commands.py
from src.handlers.command_handlers import CommandHandler

class PingCommandHandler(CommandHandler):
    command = "ping"
    description = "检查 bot 是否在线"

    def handle(self, cmd, stream_id, user_id):
        return "Pong! Bot is alive.", None

class EchoCommandHandler(CommandHandler):
    command = "echo"
    description = "回显你的消息"

    def handle(self, cmd, stream_id, user_id):
        # cmd = "echo hello world" → args = "hello world"
        args = cmd[len("echo "):].strip()
        return f"Echo: {args}", None

def register_commands(command_router):
    command_router.register(PingCommandHandler())
    command_router.register(EchoCommandHandler())
```

然后在 `bots.yaml` 中注册：

```yaml
bots:
  default:
    custom_commands:
      - "src.handlers.custom.demo_commands"
```

内置命令（无需配置）：

| 命令 | 说明 |
|------|------|
| `reset` / `清空` | 重置当前会话 |
| `help` | 显示帮助信息 |

## 飞书消息类型支持

| 类型 | 处理方式 |
|------|---------|
| `text` | 直接作为用户消息处理 |
| `post` | 提取纯文本 + 图片，合并为用户消息 |
| `image` | 下载图片，以多模态方式分析 |
| `file` | 下载文件，尝试提取文本内容 |
| `audio` | 暂不支持（未来版本） |

## 日志配置

feishu-server 支持日志级别：

```python
# src/utils/logging_config.py
import logging
logging.getLogger().setLevel(logging.DEBUG)  # 开发调试
logging.getLogger().setLevel(logging.INFO)   # 生产
```
