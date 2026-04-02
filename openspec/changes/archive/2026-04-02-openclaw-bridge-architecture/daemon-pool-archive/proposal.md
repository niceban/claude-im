## Why

当前 `wrapper.py` 每次处理消息都经历「启动 subprocess → cold start → 处理 → 销毁」，导致每条消息延迟 5-30 秒。OpenClaw 的 `input: arg` 模式每次都是独立进程，完全无法复用会话。

 clawrelay-feishu-server 的架构已经验证了热启动 session pool 的可行性：将 `ClaudeController` 保存在内存池中，新消息直接复用已有进程，实现秒级响应。

## What Changes

- **新增 HTTP Daemon 接口**：`wrapper.py` 改造为长期运行 HTTP 服务器，接收 OpenClaw 的 `/chat` 请求
- **新增 Session Pool**：内存中维护最多 10 个 `ClaudeController` 实例，按 conversation_id 路由
- **新增 LRU 驱逐**：pool 满时停止最久未使用的 controller
- **新增异步初始化**：controller 非阻塞启动，后台线程等待 init 完成
- **删除单次进程模式**：移除 `main()` 单次创建/销毁 controller 的冷启动逻辑
- **BREAKING** OpenClaw 配置变更：`input: arg` → `input: http`（或其他 HTTP 模式），`output: json` 保留

## Capabilities

### New Capabilities

- `http-daemon`: HTTP 长驻服务器，接收 JSON 请求，返回 JSON 响应，支持 `/chat` 和 `/health` 端点
- `session-pool`: per-conversation_id `ClaudeController` 内存池，线程安全，LRU 驱逐策略
- `daemon-threading`: 每 session 独立线程执行 `send()`，避免阻塞 event loop；后台 daemon 线程等待 init 完成

### Modified Capabilities

（当前无已存在的 spec，无需修改）

## Impact

- **删除**：`wrapper.py` 中的 `main()` 单次进程逻辑、`parse_input()`、`on_message()` 回调（在 daemon 模式下不再需要）
- **复用**：`config.py`（配置加载）、`error_classifier.py`（错误分类）—— 无需修改
- **复用**：`/private/tmp/claude-node/claude_node/controller.py` —— 核心不变
- **需更新**：`~/.openclaw/openclaw.json` 中 `cliBackends.claude-node-cli` 的 `input` 字段
- **归档**：`session_manager.py` 文件（文件锁方案），如果 session pool 完全替代了它的功能
