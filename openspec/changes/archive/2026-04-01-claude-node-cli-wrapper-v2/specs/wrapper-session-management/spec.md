## Capability: wrapper-session-management

### Requirement: OpenClaw 会话 ID 到 claude-node session 的映射管理

当 OpenClaw Gateway 发送请求时，wrapper 需要能够：
1. 在首次请求时启动新 claude-node session，记录 `conversation_id → session_id` 映射
2. 在后续请求中通过 `conversation_id` 找到对应的 session 并使用 `resume` 参数恢复
3. 在 session 超时或异常时清理映射

### Interface

**环境变量：**
- `CLAUDE_SESSION_MAP_FILE`：session 映射文件路径（默认 `~/.claude/sessions.json`）

**输入 JSON 格式**（stdin）：
```json
{
  "conversation_id": "abc123",
  "messages": [...],
  "resume": false
}
```

**处理逻辑：**
- 如果 `conversation_id` 已在映射中，使用 `resume=<session_id>` 启动
- 如果是新会话，启动后记录映射
- 映射文件格式：`{"conversation_id": "session_id", ...}`

### Scenario: 首次请求
- **WHEN** 用户发起新对话
- **THEN** wrapper 启动 claude-node session，记录 `conversation_id → session_id` 到映射文件

### Scenario: 恢复会话
- **WHEN** 用户继续已有对话（请求中携带 `conversation_id`）
- **THEN** wrapper 从映射文件查找 `session_id`，使用 `resume` 参数恢复会话

### Scenario: 会话清理
- **WHEN** wrapper 检测到 session 已过期或进程已退出
- **THEN** 从映射文件中删除该条目

### Boundary

- Session 映射是进程间共享的（文件），允许多个 wrapper 实例并发运行
- 映射文件读写需要加锁（flock）以避免竞态
