# 部署指南

## 飞书开放平台配置

### Step 1 — 创建自建应用

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入「开发者后台」→「创建应用」
3. 选择「企业自建应用」
4. 填写应用名称、描述，上传图标
5. 创建后进入应用详情页

### Step 2 — 获取凭证

在「凭证与基础信息」页面获取：
- **App ID**：如 `cli_a925d01967791cd5`
- **App Secret**：如 `woV3uOvc7GBI05CNhjoWGfdfuSUsYk4u`

### Step 3 — 开通权限

在「权限管理」中开通以下权限：

| 权限标识 | 类型 | 说明 |
|---------|------|------|
| `im:message` | 消息 | 获取与发送单聊、群组消息 |
| `im:message.group_at_msg` | 消息 | 接收群聊中 @ 机器人消息 |
| `im:resource` | 资源 | 获取消息中的资源文件（图片、文件） |

### Step 4 — 添加事件

在「事件与回调」中添加事件：

| 事件名 | 说明 |
|--------|------|
| `im.message.receive_v1` | 接收消息 |

### Step 5 — 启用长连接

在「事件与回调」中：
- 找到「长连接」模式
- 启用长连接（无需配置回调 URL）

### Step 6 — 发布应用

1. 在「版本管理与发布」中创建版本
2. 填写版本说明
3. 申请发布（企业内部应用无需审核，直接发布）

## 服务部署架构

### 本地开发部署

```
你的 Mac/PC
├── clawrelay-api (:50009)
└── clawrelay-feishu-server
    └── WebSocket ──▶ 飞书服务器
```

### 远程服务器部署（推荐生产使用）

```
远程服务器 (Ubuntu/CentOS)
├── clawrelay-api (:50009)
└── clawrelay-feishu-server
    └── WebSocket ──▶ 飞书服务器
         ▲
         │ SSH 隧道（可选，如需本地调试）
```

### Docker 部署（clawrelay-feishu-server）

```bash
cd ~/clawrelay-feishu-server

# 编辑配置
cp config/bots.yaml.example config/bots.yaml
vim config/bots.yaml

# 启动（注意 relay_url 改为 host.docker.internal）
docker compose up -d

# 查看日志
docker compose logs -f app
```

注意：Docker 模式下 `relay_url` 需使用 `http://host.docker.internal:50009`。

## 开机自启

### macOS LaunchAgent

```bash
cat > ~/Library/LaunchAgents/com.claude-im.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude-im</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/c/claude-im/scripts/start.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.claude-im.plist
```

### systemd (Linux)

```bash
sudo tee /etc/systemd/system/claude-im.service << 'EOF'
[Unit]
Description=Claude IM Service
After=network.target

[Service]
Type=forking
User=c
WorkingDirectory=/home/c/claude-im
ExecStart=/home/c/claude-im/scripts/start.sh
ExecStop=/home/c/claude-im/scripts/stop.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable claude-im
sudo systemctl start claude-im
```

## 安全配置

### 1. 限制允许用户

```yaml
bots:
  default:
    allowed_users:
      - "ou_xxxxxxxxxxxx"  # 飞书用户 ID
      - "ou_yyyyyyyyyyyy"
```

### 2. 注入 API Key（不依赖全局环境变量）

```yaml
bots:
  default:
    env_vars:
      ANTHROPIC_API_KEY: "sk-ant-..."
```

### 3. 限制 Claude 工作目录

```yaml
bots:
  default:
    working_dir: "/Users/c/safe-project"
```

### 4. 配置系统提示词

```yaml
bots:
  default:
    system_prompt: "你是一个助手，只回答简单问题，不执行危险操作。"
```

## 域名 / 反代配置

如果需要通过 HTTPS 暴露 API（供外部客户端使用）：

```nginx
server {
    listen 443 ssl;
    server_name api.your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:50009;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        # SSE 需要
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
    }
}
```
