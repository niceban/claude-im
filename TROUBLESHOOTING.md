# 故障排查

## 症状速查

| 症状 | 可能原因 | 快速修复 |
|------|---------|---------|
| feishu-server 启动报错 | Python 依赖未安装 | `pip install -r requirements.txt` |
| WebSocket 连接失败 | App ID/Secret 错误 | 检查 `config/bots.yaml` |
| curl 健康检查失败 | clawrelay-api 未启动 | `./clawrelay-api &` |
| 消息无回复 | `allowed_users` 白名单限制 | 清空或添加用户 ID |
| 回复极慢 | `max_turns` 过高 | 调低或 claude CLI 阻塞 |
| 工具不执行 | `bypassPermissions` 未生效 | 检查 claude 版本 |
| 会话不恢复 | session_id 为空 | 检查 feishu-server 会话逻辑 |

## 详细排查

### 1. feishu-server 无法启动

```bash
# 查看详细错误
cd ~/clawrelay-feishu-server
python3 main.py 2>&1
```

常见错误：

- **ModuleNotFoundError: No module named 'lark_oapi'**
  → `pip install lark-oapi`

- **FileNotFoundError: config/bots.yaml**
  → `cp config/bots.yaml.example config/bots.yaml`

- **YAML 解析错误**
  → 检查 YAML 缩进，使用空格而非 Tab

### 2. WebSocket 连接失败

检查日志中的错误信息：

```
[Lark] [ERROR] failed to connect to wss://msg-frontier.feishu.cn/...
```

可能原因：
- App ID 或 App Secret 错误
- 飞书应用未开通长连接权限
- 飞书应用未发布

**验证凭证**：

```python
import lark_oapi as lark

app_id = "cli_a925d01967791cd5"
app_secret = "woV3uOvc7GBI05CNhjoWGfdfuSUsYk4u"
# 测试能否获取 tenant_access_token
```

### 3. 消息发送后无回复

排查顺序：

```
Step 1: feishu-server 收到消息了吗？
  tail -f feishu-server.log | grep "收到消息"

Step 2: 调用 clawrelay-api 成功了吗？
  tail -f feishu-server.log | grep "ClaudeRelay"

Step 3: clawrelay-api 启动 claude 进程了吗？
  tail -f clawrelay-api.log | grep "Claude args"

Step 4: claude CLI 本身能跑吗？
  claude -p "1+1"（直接测试）
```

### 4. clawrelay-api 报 "claude: command not found"

```bash
# 检查 claude 是否在 PATH
which claude
claude --version

# 如果找不到，可能需要重新安装
npm install -g @anthropic-ai/claude-code
```

### 5. 会话不恢复（每次都是新对话）

检查 feishu-server 日志是否正确传递 `session_id`：

```bash
grep "session_id" ~/clawrelay-feishu-server/feishu-server.log
```

session_id 格式应为：`feishu:<user_id>:default`

### 6. 工具调用不执行

Claude 在 `bypassPermissions` 模式下应该自动执行工具。如果不执行：

```bash
# 检查 claude 版本（需要新版）
claude --version

# 检查是否有限制
claude -p "run bash: echo hello" --permission-mode bypassPermissions
```

### 7. 飞书消息限流

飞书有消息发送频率限制。如果流式编辑消息过快：

```python
# src/transport/message_dispatcher.py
# 找到节流逻辑，调整 delay
await asyncio.sleep(1.0)  # 默认 0.5s，调高到 1.0s
```

### 8. WebSocket 断线重连

feishu-server 默认有自动重连机制。检查日志：

```
[Lark] [INFO] connected to wss://msg-frontier.feishu.cn...
[Lark] [INFO] connection lost, reconnecting in 5s...
[Lark] [INFO] reconnected successfully
```

如果频繁断线：
- 网络不稳定
- 飞书服务器端有限流
- 长连接超时

## 调试模式

### 开启 feishu-server 调试日志

```python
# src/utils/logging_config.py
logging.getLogger().setLevel(logging.DEBUG)
```

### 查看 claude 原始输出

clawrelay-api 日志中包含原始 claude 输出：

```bash
grep "Claude" ~/clawrelay-api/clawrelay-api.log
```

### 模拟发送消息

直接调用 clawrelay-api：

```bash
curl -X POST http://localhost:50009/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vllm/claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "say hi"}],
    "stream": false
  }'
```

## 获取帮助

- clawrelay-api issues: https://github.com/roodkcab/clawrelay-api/issues
- clawrelay-feishu-server issues: https://github.com/wxkingstar/clawrelay-feishu-server/issues
- 飞书开放平台文档: https://open.feishu.cn/document/home
