## Context

**现状**：`wrapper.py` 的 `main()` 函数每次被调用都执行「创建 `ClaudeController` → cold start subprocess → `send()` → `stop()` → 进程退出」。OpenClaw 的 `input: arg` 模式每条消息独立进程，无任何会话复用。

**目标状态**：Daemon 模式 —— `wrapper.py` 作为 Long-running HTTP 服务器启动，接收请求时从内存池取出一个已启动的 `ClaudeController`（热启动），处理完不销毁，复用下次请求。

**参考架构**：已归档的 `clawrelay-feishu-server/src/adapters/claude_node_adapter.py` 中的 `ClaudeNodeAdapter` 类，已实现完整 session pool + LRU + 异步 init。

## Goals / Non-Goals

**Goals:**
- HTTP 长驻服务器，监听一个可配置端口（默认 18790）
- `/chat` 端点：接收 `{"conversation_id": "", "messages": [...], "resume": bool}`，返回 JSON 结果
- `/health` 端点：健康检查，返回 `{"ok": true, "pool_size": N}`
- 最多 10 个 `ClaudeController` 实例的内存池
- LRU 驱逐策略：pool 满时停止最久未使用的 controller
- 非阻塞启动：`start(wait_init_timeout=0)` + 后台 daemon 线程等待 init 完成
- 线程安全：每 session 有独立 `threading.RLock`，pool 操作有全局锁

**Non-Goals:**
- 不实现 WebSocket 流式（当前 OpenClaw cliBackends HTTP 模式不支持流式响应）
- 不改变 OpenClaw 的 `reusableCliSession` 机制（session ID 复用由 OpenClaw 控制）
- 不迁移文件锁 `SessionMap`：session 路由完全由 daemon 内存池管理
- 不改变 `config.py` 和 `error_classifier.py`（保持复用）

## Decisions

### Decision 1: HTTP 服务器框架 —— 纯 Python stdlib vs 添加依赖

**选择**：纯 Python `http.server` 模块，不引入 Flask/FastAPI 依赖。

**理由**：wrapper 已经依赖 claude-node，不需要额外的 HTTP 框架。`http.server.HTTPServer` + `threading` 足够满足需求，零额外依赖。

### Decision 2: Daemon 端口配置方式

**选择**：通过环境变量 `CLAUDE_DAEMON_PORT` 配置，默认 `18790`。

**理由**：与 OpenClaw 配置体系一致，通过 env var 注入，无需修改代码。

### Decision 3: Session Pool 大小

**选择**：`MAX_POOL_SIZE = 10`（与 clawrelay 一致）。

**理由**：经验值，足够覆盖日常使用场景。超出时 LRU 驱逐。

### Decision 4: Controller 初始化策略

**选择**：`ctrl.start(wait_init_timeout=0)` 非阻塞启动，后台 `threading.Thread` 等待 init 完成（最多 30s）。

**理由**：避免 HTTP 请求被阻塞在启动阶段。daemon thread 在后台等待，HTTP handler 在 controller 未 init 完成时等待或返回错误。

### Decision 5: 输入解析（废弃）

**删除**：`parse_input()`、`on_message()` 回调、`_streaming_enabled` 全局状态。

**理由**：在 Daemon HTTP 模式下，请求通过 JSON body 传入，响应通过 JSON body 返回，无需 streaming JSONL 解析。streaming 逻辑在 HTTP 模式下不适用。

### Decision 6: SessionMap 文件锁（降级）

**决策**：`session_manager.py` 的 `SessionMap` 类降级为**可选**（session 路由由 daemon 内存池处理，不再需要文件锁映射）。如果实现中发现 OpenClaw 需要从外部追踪 session 映射，再重新启用。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| OpenClaw 的 `input: http` 模式与设想不兼容 | 先小规模测试 HTTP 接口，确认 OpenClaw 请求格式后再全量切换 |
| Pool 中 controller 内存累积 | LRU 驱逐 + 最大 10 个上限；每个 controller 是一个 subprocess，内存可控 |
| `/new` 命令后 session 状态不一致 | daemon 内存池无法感知 OpenClaw 的 `system-prompt` 哈希变化；需要在 HTTP 接口层面支持显式 `resume` 标志，或驱逐特定 session |
| HTTP 服务器单点故障导致所有 session 丢失 | 长期看需要进程管理（launchd 或 systemd）保活；短期内 daemon crash 后 OpenClaw 会重启进程并重建 pool |
| controller subprocess 假死（alive=True 但不响应） | `_ensure_controller_alive()` 仅检查 `poll()`，无法检测死锁；通过 timeout 保护 HTTP 请求 |
