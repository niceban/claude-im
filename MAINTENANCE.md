# 运维指南

## 服务管理

### 查看服务状态

```bash
# 检查进程
ps aux | grep clawrelay-api | grep -v grep
ps aux | grep "python3 main.py" | grep -v grep

# 检查端口
lsof -i :50009

# 检查健康
curl http://localhost:50009/health
```

### 查看日志

```bash
# clawrelay-api 日志
tail -f ~/clawrelay-api/clawrelay-api.log

# feishu-server 日志
tail -f ~/clawrelay-feishu-server/feishu-server.log

# 最近 100 行
tail -100 ~/clawrelay-feishu-server/feishu-server.log
```

### 重启服务

```bash
# 停止
pkill -f "clawrelay-api"
pkill -f "python3 main.py"

# 启动
cd ~/clawrelay-api && nohup ./clawrelay-api > clawrelay-api.log 2>&1 &
cd ~/clawrelay-feishu-server && nohup python3 main.py > feishu-server.log 2>&1 &
```

或使用脚本：

```bash
~/claude-im/scripts/restart.sh
```

## clawrelay-api 调试

### 查看活跃会话

```bash
curl http://localhost:50009/sessions
```

### 打开会话查看器

浏览器访问：`http://localhost:50009/session/<session_id>`

### 查看 Token 统计

```bash
curl http://localhost:50009/v1/stats
```

响应：

```json
{
  "total_requests": 42,
  "input_tokens": 15000,
  "output_tokens": 8000,
  "total_tokens": 23000,
  "per_model": {
    "sonnet": {
      "requests": 30,
      "input_tokens": 12000,
      "output_tokens": 6000
    }
  },
  "start_time": "2026-03-09T10:00:00Z",
  "uptime": "2h30m"
}
```

## 会话管理

### 会话文件位置

```
~/clawrelay-api/sessions/
```

### 手动清理会话

```bash
# 删除特定用户的会话
rm ~/clawrelay-api/sessions/feishu:ou_xxxxx:default.jsonl

# 删除所有会话（谨慎！）
rm ~/clawrelay-api/sessions/*.jsonl

# 删除 N 天前的会话
find ~/clawrelay-api/sessions/ -name "*.jsonl" -mtime +30 -delete
```

### 会话大小监控

```bash
du -sh ~/clawrelay-api/sessions/
```

## 日志管理

### 聊天日志位置

```
~/clawrelay-feishu-server/logs/
```

每条消息记录为 JSONL：

```jsonl
{"event":"user_message","user_id":"ou_xxx","time":"...","content":"..."}
{"event":"bot_response","user_id":"ou_xxx","time":"...","content":"..."}
```

### 日志轮转

建议配合 `logrotate`：

```bash
# /etc/logrotate.d/claude-im
~/clawrelay-api/clawrelay-api.log ~/clawrelay-feishu-server/feishu-server.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

## 升级

### 升级 clawrelay-api

```bash
cd ~/clawrelay-api
git pull
go build -o clawrelay-api .
pkill -f "clawrelay-api"
nohup ./clawrelay-api > clawrelay-api.log 2>&1 &
```

### 升级 feishu-server

```bash
cd ~/clawrelay-feishu-server
git pull
pip install -r requirements.txt
pkill -f "python3 main.py"
nohup python3 main.py > feishu-server.log 2>&1 &
```

### 升级 Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
claude --version
pkill -f "clawrelay-api"  # 重启以使用新版本
```

## 监控

### Health Check 脚本

```bash
#!/bin/bash
HEALTH=$(curl -s http://localhost:50009/health)
if [[ "$HEALTH" == *"healthy"* ]]; then
    echo "✅ clawrelay-api 健康"
    exit 0
else
    echo "❌ clawrelay-api 异常: $HEALTH"
    exit 1
fi
```

### 进程守护脚本（supervisor）

```ini
# /etc/supervisor/conf.d/claude-im.conf
[program:clawrelay-api]
command=/home/c/clawrelay-api/clawrelay-api
directory=/home/c/clawrelay-api
user=c
autostart=true
autorestart=true
stderr_logfile=/var/log/claude-im/api.err.log
stdout_logfile=/var/log/claude-im/api.out.log

[program:clawrelay-feishu]
command=/usr/bin/python3 /home/c/clawrelay-feishu-server/main.py
directory=/home/c/clawrelay-feishu-server
user=c
autostart=true
autorestart=true
stderr_logfile=/var/log/claude-im/feishu.err.log
stdout_logfile=/var/log/claude-im/feishu.out.log
```

## 性能调优

| 参数 | 默认值 | 调优建议 |
|------|--------|---------|
| `--max-turns` | 200 | 降低可减少单次响应时间，但限制工具调用能力 |
| 500ms 节流 | 500ms | 网络差可调高到 1000ms，减少消息更新频率 |
| `working_dir` | sessions/ | 设置固定项目目录可提升上下文相关性 |
