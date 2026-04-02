## Capability: wrapper-error-classification

### Requirement: 错误分类与结构化返回

wrapper 需要区分三类错误，并在返回给 OpenClaw 时使用不同的 error_code：

### 错误分类

| 类别 | error_code | 说明 | 返回内容 |
|------|-----------|------|---------|
| API Error | `101` | API 认证失败、rate limit、无效请求 | `result_text` 包含错误描述 |
| Tool Failure | `102` | 工具执行失败（权限拒绝、文件不存在等） | `tool_errors` 数组 |
| Process Error | `103` | claude-node 进程异常（crash、timeout、启动失败） | `stderr` 内容 |
| Configuration Error | `104` | 环境变量配置错误、路径无效 | 错误描述 |

### 返回格式（stdout）

```json
{
  "type": "result",
  "text": "用户看到的回复内容",
  "error": null,
  "error_code": null,
  "session_id": "sess_xxx",
  "tool_errors": [],
  "api_error": false,
  "total_cost_usd": 0.001,
  "num_turns": 3
}
```

错误时：
```json
{
  "type": "result",
  "text": "",
  "error": "API Error: Rate limit exceeded",
  "error_code": 101,
  "session_id": "sess_xxx",
  "tool_errors": [],
  "api_error": true,
  "total_cost_usd": 0.0005,
  "num_turns": 1
}
```

### Scenario: API 错误
- **WHEN** claude 返回 `result_text` 以 "API Error:", "Rate limit", "Not logged in" 开头
- **THEN** error_code=101, api_error=true

### Scenario: 工具执行失败
- **WHEN** `get_tool_errors()` 返回非空数组
- **THEN** error_code=102, tool_errors=[...]

### Scenario: 进程超时
- **WHEN** `send()` 超时返回 None
- **THEN** error_code=103, error="Request timeout"

### Scenario: 配置错误
- **WHEN** 启动时检查发现 `CLAUDE_NODE_PATH` 无效
- **THEN** error_code=104, 立即返回错误，不启动进程

### Boundary

- tool_errors 仅收集 `is_error=true` 的 tool_result blocks
- timeout 时不改变 session 状态（可 retry）
