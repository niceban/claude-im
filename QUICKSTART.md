# 快速启动

## 环境要求

- **Go 1.21+** — 编译 clawrelay-api
- **Python 3.12+** — 运行 feishu-server
- **Node.js** — Claude Code CLI 已安装
- **Claude Code CLI** — 已配置 API Key
- **飞书自建应用** — App ID + App Secret

## Step 1 — 克隆 clawrelay-api

```bash
git clone https://github.com/roodkcab/clawrelay-api.git ~/clawrelay-api
cd ~/clawrelay-api
go build -o clawrelay-api .
```

验证：
```bash
./clawrelay-api &
sleep 1
curl http://localhost:50009/health
# {"claude":"available","status":"healthy"}
```

## Step 2 — 克隆 feishu-server

```bash
git clone https://github.com/wxkingstar/clawrelay-feishu-server.git ~/clawrelay-feishu-server
cd ~/clawrelay-feishu-server
pip install -r requirements.txt
```

## Step 3 — 配置飞书 Bot

```bash
cp config/bots.yaml.example config/bots.yaml
```

编辑 `config/bots.yaml`：

```yaml
bots:
  default:
    app_id: "cli_a925d01967791cd5"       # 替换为你的 App ID
    app_secret: "woV3uOvc7GBI05CNhjo..." # 替换为你的 App Secret
    relay_url: "http://localhost:50009"
    name: "Claude Bot"                    # 机器人名称
    description: "Claude Code Bot"
    model: "vllm/claude-sonnet-4-6"      # 模型
    working_dir: ""                        # Claude 工作目录（留空用默认）
    system_prompt: ""
    allowed_users: []                      # 白名单（留空不限制）
    env_vars: {}
```

## Step 4 — 配置 Claude API Key

clawrelay-api 通过环境变量将 `ANTHROPIC_API_KEY` 传递给 claude 子进程。

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

或在 `config/bots.yaml` 中注入：

```yaml
env_vars:
  ANTHROPIC_API_KEY: "sk-ant-..."
```

**检查现有配置**：
```bash
# 查看当前 API profile
cat ~/.claude/api-profiles/*.json

# 查看 ANTHROPIC 相关 env
env | grep ANTHROPIC
```

## Step 5 — 启动服务

**方式 A — 手动启动（开发调试）**：

```bash
# 终端 1: 启动 clawrelay-api
cd ~/clawrelay-api && ./clawrelay-api

# 终端 2: 启动 feishu-server
cd ~/clawrelay-feishu-server && python3 main.py
```

**方式 B — 后台运行（生产环境）**：

```bash
# 启动 clawrelay-api
cd ~/clawrelay-api
nohup ./clawrelay-api > clawrelay-api.log 2>&1 &

# 启动 feishu-server
cd ~/clawrelay-feishu-server
nohup python3 main.py > feishu-server.log 2>&1 &
```

**方式 C — 使用项目脚本**（见 scripts/ 目录）

## Step 6 — 验证服务状态

```bash
# 检查 clawrelay-api 健康
curl http://localhost:50009/health

# 检查端口占用
lsof -i :50009

# 查看 feishu-server 日志
tail -f ~/clawrelay-feishu-server/feishu-server.log
```

成功标志：
```
[Lark] connected to wss://msg-frontier.feishu.cn/ws/v2...
```

## Step 7 — 测试

1. 打开飞书，找到你的自建应用机器人
2. 给机器人发送一条消息，如：`你好`
3. 等待回复（首次响应可能需要 5-10 秒）

## 测试 Claude CLI 连通性

```bash
# 手动测试 claude CLI 是否正常工作
claude -p "1+1等于几"

# 测试流式输出
curl -X POST http://localhost:50009/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vllm/claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "Say hello in 3 words"}],
    "stream": true
  }'
```

## 常见启动问题

详见 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
