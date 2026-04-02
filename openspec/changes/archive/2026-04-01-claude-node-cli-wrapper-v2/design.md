## Context

当前 wrapper.py（v1）的问题：

```python
# v1: 只传了 prompt，其他全丢失
controller = ClaudeController(
    skip_permissions=True,
    cwd=os.environ.get('CLAUDE_CWD', None),  # 环境变量未设置，永远是 None
)
result = controller.send(user_text, timeout=300.0)
```

claude-node 的 `ClaudeController` API 支持完整能力：

```python
ClaudeController(
    cwd="/Users/c/claude-im",                    # 工作目录
    tools=["Bash", "Read", "Write", ...],       # 工具链
    add_dirs=["/Users/c/.claude/skills"],        # 额外上下文
    model="claude-sonnet-4-6",                  # 模型
    skip_permissions=True,                        # 跳过交互确认
    resume=session_id,                           # 恢复会话
    # + stream-json 事件回调
)
```

**关键问题**：OpenClaw Gateway 的 WebSocket 协议是否支持 streaming 事件推送？这是核心依赖。

## Goals / Non-Goals

**Goals:**
- 配置驱动：所有参数通过 `CLAUDE_*` 环境变量配置
- 完整工具链：启用 Claude Code CLI 内置工具 + MCP 工具
- Session 持久化：支持 OpenClaw session_id ↔ claude-node session 映射
- 中间事件可见：tool_use / tool_result / task_progress 推送回 OpenClaw
- 错误分类：区分 API error / tool failure / process error

**Non-Goals:**
- 不修改 OpenClaw Gateway 本身（若 Gateway 不支持 streaming events，则降级为纯 result 文本）
- 不实现多会话并发管理（单进程单会话，通过 OpenClaw 路由区分）
- 不替代 OpenClaw 的 cliBackends 配置机制（配置仍由 openclaw.json 定义）

## Decisions

### D1: 配置来源 — 环境变量 vs openclaw.json

**决定**：通过环境变量传递配置

**理由**：
- OpenClaw 的 cliBackends 机制支持在 `env` 字段中声明环境变量
- 环境变量对进程级配置最简洁
- 避免 wrapper.py 直接解析 JSON

**替代方案考虑**：
- 直接解析 openclaw.json：增加对配置格式的耦合，不灵活
- 通过 CLI 参数传递：wrapper.py 是被调用的 CLI，目标是无状态单次调用，环境变量更合适

### D2: Session 管理 — OpenClaw session_id ↔ claude-node session

**决定**：使用 `resume` 参数在首次和后续请求间建立关联

**理由**：
- claude-node 支持通过 `resume=session_id` 恢复历史会话
- OpenClaw 在每次请求中携带 `conversation_id`
- 第一次请求时创建 session 并返回 session_id；后续请求用 `conversation_id` 作为 `resume` 参数

**关键**：需要在 wrapper 进程内维护一个 `conversation_id → session_id` 的映射（内存 dict 或磁盘文件）

### D3: 事件流推送 — streaming vs polling

**决定**：如果 OpenClaw Gateway 支持 WebSocket push-back，则用 streaming；否则降级为纯 result 文本

**Open Question**：OpenClaw 的 cliBackends 协议是否支持服务端 push（streaming events）？

- **如果支持**：通过 `on_message` 回调将事件写入 stdout/stderr（已分流），或通过某个回调 channel 推送回 OpenClaw
- **如果不支持**：退化为当前行为 — 只等 result 并返回最终文本

### D4: 工具链配置 — 显式声明 vs 默认全部

**决定**：通过 `CLAUDE_TOOLS` 环境变量声明，默认为 `Bash,Read,Write,Glob,Grep,WebFetch,Agent,Task,TaskOutput`

**理由**：
- 安全边界：Feishu 用户不应有不受限的 Bash 权限
- 可配置：运维可通过 openclaw.json 控制允许的工具列表

### D5: 进程生命周期 — 每次请求 spawn vs 持久进程

**决定**：每次请求 spawn 新进程，请求结束后立即 stop

**理由**：
- 简单：避免进程管理复杂性
- 安全：每次请求独立进程，无状态泄漏风险
- Session 复用：通过 `resume` 参数而非持久进程来维持上下文

## Risks / Trade-offs

| 风险 | 影响 |  Mitigation |
|------|------|------------|
| OpenClaw Gateway 不支持 streaming events | 中间事件丢失，用户体验降级 | 降级为纯文本，做好错误处理 |
| tool 调用权限过大 | 安全风险 | 通过 `CLAUDE_TOOLS` 白名单限制 |
| session 映射内存泄漏 | 长时间运行后内存膨胀 | 使用 LRU cache 或定期清理 |
| 首次请求冷启动慢 | 等待时间长 | 预热进程（可选优化） |

## Open Questions

1. **OpenClaw Gateway 是否支持 streaming events back**？这决定了是否需要修改 OpenClaw 本身
2. **`CLAUDE_CWD` 默认值**：应为 `/Users/c` 还是更具体的目录（如项目根目录）？
3. **session 映射持久化**：内存 dict 在进程退出后丢失，是否需要持久化到磁盘？
