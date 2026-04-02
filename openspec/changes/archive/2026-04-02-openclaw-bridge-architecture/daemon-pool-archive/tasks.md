## 1. Code Audit & Deletion（清理废弃代码）

- [x] 1.1 删除 `wrapper.py` 中的 `parse_input()` 函数（HTTP 模式下不再需要 CLI arg/stdin 解析）
- [x] 1.2 删除 `wrapper.py` 中的 `on_message()` 回调（HTTP 模式不需要 JSONL streaming）
- [x] 1.3 删除 `_streaming_enabled` 全局状态和相关逻辑
- [x] 1.4 删除 `main()` 函数中的冷启动单次进程逻辑（controller 创建/启动/发送/停止/退出序列），替换为 `daemon.run_daemon()` 调用
- [x] 1.5 保留并复用 `config.py`（无需修改）
- [x] 1.6 保留并复用 `error_classifier.py`（无需修改）
- [ ] 1.7 评估 `session_manager.py` 的 SessionMap 是否还需要（session 路由由 daemon 内存池接管，可选降级）

## 2. Session Pool 实现

- [x] 2.1 添加 pool 数据结构：`_controllers`, `_controller_locks`, `_controller_last_used`, `_pool_lock`
- [x] 2.2 实现 `_evict_lru_if_needed()`：当 pool size >= MAX_POOL_SIZE 时驱逐 LRU controller
- [x] 2.3 实现 `_ensure_controller_alive(session_key)`：检查 subprocess 是否存活，dead 时清理并返回 False
- [x] 2.4 实现 `_get_controller(session_key, system_prompt, resume)`：fast path 取缓存，slow path 创建并添加 LRU 驱逐
- [x] 2.5 实现 `prewarm()`：启动时预热 `_default` session controller

## 3. HTTP Daemon 实现

- [x] 3.1 使用 Python stdlib `http.server.HTTPServer` + `threading.Thread` 实现 HTTP 服务器
- [x] 3.2 读取 `CLAUDE_DAEMON_PORT` 环境变量，默认 `18790`
- [x] 3.3 实现 `/health` 端点：返回 `{"ok": true, "pool_size": N}`
- [x] 3.4 实现 `/chat` 端点：接收 JSON body，路由到 session pool，返回结果 JSON
- [x] 3.5 启动时调用 `validate_config()`，验证失败则退出并输出错误到 stderr

## 4. Daemon Threading 模型

- [x] 4.1 调用 `ctrl.start(wait_init_timeout=0)` 非阻塞启动
- [x] 4.2 后台 daemon thread 等待 init 完成（最多 30s），超时则 log warning
- [x] 4.3 HTTP handler 中若 controller init 未完成，等待最多 10s，超时返回 PROCESS_ERROR
- [x] 4.4 每个 `/chat` 请求由独立线程执行 `controller.send()`（线程池或直接 Thread）
- [x] 4.5 注册 `SIGTERM`/`SIGINT` handler：设置 `_shutdown_requested`，停止所有 pooled controllers，优雅退出

## 5. OpenClaw 配置更新

- [ ] 5.1 更新 `~/.openclaw/openclaw.json`：`cliBackends.claude-node-cli` 的 `input` 从 `arg` 改为 HTTP 模式（待确认 OpenClaw 支持的 HTTP input 模式具体值）
- [ ] 5.2 更新 `command`/`args` 指向 daemon 监听地址（如 `http://localhost:18790/chat`）
- [ ] 5.3 本地测试 daemon HTTP 接口与 OpenClaw 的集成

## 6. TDD 测试

- [x] 6.1 测试 session pool LRU 驱逐：当 pool 满时，第 11 个 session 触发驱逐最旧 controller
- [x] 6.2 测试 controller death 检测：subprocess 崩溃后自动重建
- [x] 6.3 测试非阻塞启动：daemon 启动后立即返回，不卡住主线程
- [ ] 6.4 测试 `/health` 端点返回 pool size
- [ ] 6.5 测试 `/chat` 端点：正常对话流程，验证 session 复用
- [ ] 6.6 测试 `/chat` 端点：session 不存在时自动创建并启动新 controller
- [ ] 6.7 测试 timeout 场景：send 超时时返回 PROCESS_ERROR
- [ ] 6.8 测试 SIGTERM 优雅退出：所有 pooled controllers 被停止
