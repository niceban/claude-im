## 1. Setup & Infrastructure

- [x] 1.1 创建新的 `wrapper.py` 文件（v2），从 `claude_node.controller` 导入
- [x] 1.2 创建 `session_manager.py` — session 映射管理模块
- [x] 1.3 创建 `config.py` — 环境变量配置读取与验证模块
- [x] 1.4 创建 `error_classifier.py` — 错误分类模块

## 2. Config Module (config.py)

- [x] 2.1 实现 `load_config()` — 从环境变量读取所有配置项
- [x] 2.2 实现 `validate_paths()` — 验证 `CLAUDE_NODE_PATH` 和 `CLAUDE_CWD` 有效性
- [x] 2.3 实现 `parse_tools()` — 解析逗号分隔的工具列表
- [x] 2.4 实现 `check_claude_binary()` — 检查 claude binary 可用性

## 3. Session Manager (session_manager.py)

- [x] 3.1 设计 session 映射文件格式（JSON：`conversation_id → session_id`）
- [x] 3.2 实现 `SessionMap` 类 — 文件读写 + flock 锁
- [x] 3.3 实现 `get_session_id(conversation_id)` — 查询映射
- [x] 3.4 实现 `register_session(conversation_id, session_id)` — 注册新映射
- [x] 3.5 实现 `remove_session(conversation_id)` — 删除映射（清理时调用）

## 4. Error Classifier (error_classifier.py)

- [x] 4.1 定义 ERROR_CODES 常量（101-104）
- [x] 4.2 实现 `classify_error(result, tool_errors)` — 判定错误类型
- [x] 4.3 实现 `make_result_response()` — 构造标准返回 JSON

## 5. Core Wrapper Logic (wrapper.py 主逻辑)

- [x] 5.1 解析 stdin 输入 JSON（支持 `input:arg` 和 `input:stdin` 两种模式）
- [x] 5.2 初始化 Config 并验证
- [x] 5.3 查询或注册 session（SessionMap）
- [x] 5.4 构造 `ClaudeController` 参数（cwd、tools、add_dirs、model、resume）
- [x] 5.5 实现 `on_message` 回调 — streaming 事件输出到 stdout
- [x] 5.6 调用 `controller.send()` 并收集结果
- [x] 5.7 分类错误并构造返回 JSON
- [x] 5.8 实现 SIGTERM/SIGINT 信号处理（graceful shutdown）

## 6. Streaming Events (wrapper.py Streaming)

- [x] 6.1 实现 `write_event(event_type, data)` — JSONL 格式化输出
- [x] 6.2 处理 `assistant` 事件 — 输出 text blocks
- [x] 6.3 处理 `tool_use` 事件 — 输出工具调用
- [x] 6.4 处理 `user` (tool_result) 事件 — 输出工具结果
- [x] 6.5 处理 `system/task_*` 事件 — 输出进度通知
- [x] 6.6 实现降级模式（`CLAUDE_STREAM_EVENTS=false` 时跳过中间事件）

## 7. openclaw.json Configuration

- [x] 7.1 在 `cliBackends.claude-node-cli.env` 中添加所有新的环境变量
- [x] 7.2 配置 `CLAUDE_TOOLS` 白名单
- [x] 7.3 配置 `CLAUDE_CWD` 为项目目录
- [x] 7.4 配置 `CLAUDE_SKIP_PERMISSIONS=true`

## 8. Testing

- [x] 8.1 测试首次会话创建 + session 映射记录
- [x] 8.2 测试会话恢复（resume）
- [x] 8.3 测试 streaming 模式输出
- [x] 8.4 测试降级模式（streaming disabled）
- [x] 8.5 测试 API 错误分类（rate limit / auth failure）
- [x] 8.6 测试工具执行失败分类（permission denied）
- [x] 8.7 测试配置错误（无效 CLAUDE_NODE_PATH）
- [x] 8.8 测试超时处理
- [ ] 8.9 端到端测试：Gateway → wrapper → claude-node → 返回结果

## 9. Deployment

- [x] 9.1 替换 `/Users/c/claude-node-cli-wrapper.py` 为 v2
- [x] 9.2 更新 `~/.openclaw/openclaw.json` 环境变量
- [x] 9.3 重启 OpenClaw Gateway
- [ ] 9.4 验证 Gateway → wrapper → claude-node 完整链路

## 10. 验证修复 (Verification Fixes)

- [x] 10.1 修复：openclaw.json 中 `output: "json"` 与 `CLAUDE_STREAM_EVENTS: "true"` 不兼容
  - 原因：`output: "json"` 模式下 Gateway 的 `parseCliJson` 期望单个完整 JSON 对象，但 streaming 模式输出多行 JSONL
  - 修复：设置 `CLAUDE_STREAM_EVENTS: "false"`，wrapper 仅输出最终结果 JSON
- [x] 10.2 修复：openclaw.json 添加 `sessionIdFields` 确保 Gateway 能从 wrapper 结果中提取 session_id
- [x] 10.3 验证：Gateway 配置变更已被正确加载（从 gateway.log 确认）
- [x] 10.4 验证：wrapper 直接调用测试通过（单行 JSON 输出格式正确）
