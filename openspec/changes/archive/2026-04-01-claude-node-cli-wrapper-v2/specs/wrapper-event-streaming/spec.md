## Capability: wrapper-event-streaming

### Requirement: 将 claude-node 的中间事件推送回 OpenClaw Gateway

通过 `ClaudeController` 的 `on_message` 回调接收所有事件，并根据类型处理：

### 事件分类与处理

| 事件类型 | 处理方式 |
|---------|---------|
| `system/init` | 忽略（启动确认） |
| `assistant` | 提取 `text` blocks，通过 stdout 写回 OpenClaw |
| `tool_use` | 提取工具名和参数，通过 stdout 写回 OpenClaw |
| `user` (tool_result) | 提取执行结果，写回 OpenClaw |
| `system/task_*` | 提取描述，写回 OpenClaw |
| `result` | 提取最终回复，写回 OpenClaw，结束请求 |

### 事件格式（stdout JSONL）

每行一个 JSON 对象：
```json
{"type": "assistant", "content": [{"type": "text", "text": "..."}]}
{"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}
{"type": "tool_result", "content": "total 64\ndrwxr-xr-x  ..."}
{"type": "result", "text": "最终回复内容", "session_id": "sess_xxx"}
```

### OpenClaw Gateway 兼容性

**Open Question**：如果 OpenClaw Gateway 的 cliBackends 协议不支持接收 streaming events，退化为：
- 不输出中间事件
- 只在最后输出 `{"type": "result", ...}`

可通过环境变量 `CLAUDE_STREAM_EVENTS=false` 禁用 streaming。

### Scenario: Streaming 模式
- **WHEN** `CLAUDE_STREAM_EVENTS=true` 且 Gateway 支持
- **THEN** 每个中间事件都通过 stdout JSONL 写回

### Scenario: 降级模式
- **WHEN** `CLAUDE_STREAM_EVENTS=false` 或 Gateway 不支持
- **THEN** 只在最后输出 result，中间事件忽略

### Boundary

- Streaming 模式下，stdout 同时用于协议输出，需要确保 JSONL 格式与 OpenClaw 协议兼容
- stderr 保留用于调试日志
