# 架构详解

## 系统全景

```
┌──────────────────────────────────────────────────────────────────┐
│                            飞书用户                               │
│                   (单聊 / 群聊 @机器人)                           │
└────────────────────────────┬─────────────────────────────────────┘
                             │ 飞书 WebSocket 协议
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│              clawrelay-feishu-server (Python)                     │
│                                                                  │
│  ┌──────────────┐  ┌─────────────────┐  ┌────────────────────┐  │
│  │ FeishuWs    │  │ MessageDispatcher│  │ ClaudeRelayAdapter │  │
│  │ 长连接管理    │──▶│ 消息路由/节流     │──▶│ SSE 调用 clawrelay  │  │
│  │ 心跳/重连    │  │ 命令处理         │  │ 流式响应解析       │  │
│  └──────────────┘  └─────────────────┘  └────────────────────┘  │
│                            │                                       │
│                     ┌──────▼──────┐                               │
│                     │ SessionMgr   │  内存会话/自动过期              │
│                     │ ChatLogger   │  JSONL 日志                   │
│                     └─────────────┘                               │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP + SSE
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    clawrelay-api (Go, :50009)                     │
│                                                                  │
│  ┌──────────────┐  ┌─────────────────┐  ┌────────────────────┐  │
│  │ OpenAI API   │  │ Message→Prompt  │  │ ClaudeCLILauncher  │  │
│  │ /v1/chat/... │──▶│ 格式转换        │──▶│ spawn claude 进程   │  │
│  │ /v1/models   │  │ 图片解码→临时文件 │  │ stdin/stdout pipe  │  │
│  └──────────────┘  └─────────────────┘  └────────────────────┘  │
│                                                         │        │
│                     ┌──────────────┐                    │        │
│                     │ SessionStore │◀──────────── stdin  │        │
│                     │ JSONL 文件    │        stream-json ▼        │
│                     └──────────────┘         ┌──────────────┐   │
│                                               │  Claude CLI   │   │
│                                               │  真正执行内核  │   │
│                                               └──────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## 消息处理流程

### 1. 消息接收（飞书 → feishu-server）

```
飞书服务器 ──WebSocket──▶ Lark SDK ──▶ FeishuWsClient
                                    │
                                    ▼
                            MessageDispatcher
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
         text 类型         post 类型         image 类型
            │                 │                 │
            ▼                 ▼                 ▼
      检查内置命令      提取文本+图片     下载+多模态分析
    (reset/help/...)   统一走 text      转 text 走相同流程
```

### 2. AI 调用（feishu-server → clawrelay-api → Claude）

```
feishu 消息文本
    │
    ▼
构造 OpenAI /v1/chat/completions 请求体：
{
  "model": "vllm/claude-sonnet-4-6",
  "messages": [{"role": "user", "content": "..."}],
  "stream": true,
  "session_id": "<user_id>",
  "working_dir": "",
  "env_vars": {}
}
    │
    ▼
SSE POST http://localhost:50009/v1/chat/completions
    │
    ▼
clawrelay-api 解析请求：
  1. messages → prompt 字符串
  2. 启动 claude 子进程：
     claude --model sonnet-4-6 \
            --append-system-prompt "..." \
            --output-format stream-json \
            --include-partial-messages \
            --permission-mode bypassPermissions \
            --max-turns 200 \
            --resume <session_id>
  3. stdin 写入 prompt
    │
    ▼
Claude CLI 执行（真正 AI 推理 + 工具调用）
    │
    ▼
stdout 输出 stream-json：
  { "type": "content_block_delta", "delta": { "type": "thinking_delta", "thinking": "..." } }
  { "type": "content_block_delta", "delta": { "type": "text_delta", "text": "..." } }
  { "type": "content_block_delta", "delta": { "type": "tool_use", "id": "...", "name": "Bash", "input": "..." } }
  ...
    │
    ▼
clawrelay-api 解析 → SSE 格式：
  data: {"id":"...","choices":[{"delta":{"thinking":"..."}}]}
  data: {"id":"...","choices":[{"delta":{"content":"..."}}]}
  data: {"id":"...","choices":[{"delta":{"tool_calls":[{"id":"...","function":{"name":"Bash","arguments":"{...}"}}]}}]}
```

### 3. 流式响应推送（clawrelay-api → feishu-server → 用户）

```
SSE 流 ──▶ ClaudeRelayAdapter
                │
                ▼ 500ms 节流
         FeishuAPI 编辑消息
         (im.message.update)
                │
                ▼
         飞书用户看到打字效果
```

**500ms 节流机制**：避免消息更新过快导致飞书限流，同时保证实时性。

## 会话管理

### 会话隔离策略

每个飞书用户/群组 → 独立 `session_id` → 独立 Claude 工作目录：

```
feishu user_id: ou_xxxxx
    │
    ▼
session_id = "feishu:ou_xxxxx:default"
    │
    ▼
--working-dir = ""（使用 clawrelay-api 默认 sessions/ 目录）
--resume = "feishu:ou_xxxxx:default"
    │
    ▼
Claude CLI 的 --resume 恢复该用户的对话历史
```

### 会话过期策略

- **内存会话**：feishu-server 内存管理，自动过期
- **持久会话**：clawrelay-api 的 `sessions/` 目录 JSONL 文件

## 工具调用流程

Claude CLI 的工具调用（bash/write/edit/mcp）在 `bypassPermissions` 模式下**直接执行**，无需用户审批：

```
Claude 决定执行 Bash: ls -la
    │
    ▼  stream-json
clawrelay-api 收到 tool_use
    │
    ▼  SSE delta.tool_calls
feishu-server 收到
    │
    ▼
（不等待用户审批，直接执行）
    │
    ▼
结果通过 tool_result 传回 Claude
    │
    ▼
最终文本回复推送给飞书用户
```

## 安全边界

```
飞书用户消息文本
    │
    ▼
feishu-server：
  • 基础输入验证
  • allowed_users 白名单过滤
  • 命令前缀检测（reset/help/...）
    │
    ▼
clawrelay-api（envVars 注入）：
  • 不信任的 env_vars 可控
  • CLAUDECODE env 被过滤
    │
    ▼
Claude CLI（bypassPermissions）：
  • 工具直接执行，无审批
  • --max-turns 限制自主循环次数
  • 每个用户独立 session
```

**关键风险**：`bypassPermissions` 意味着任何能发消息给 bot 的用户都可以触发工具执行。生产环境必须配置 `allowed_users` 白名单。
