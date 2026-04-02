## Why

当前的 `wrapper.py` 没有正确使用 `claude-node` 的 API，导致 Feishu bot 只能获得裸文本回复，无法发挥 Claude Code CLI 的完整 agent 能力（工具链、session 持久化、上下文管理等）。需要在 OpenClaw Gateway 和 claude-node 之间建立真正的 full-agent 集成。

## What Changes

- **配置驱动**：wrapper.py 从环境变量读取完整配置（cwd、tools、add-dirs、model、permission-mode），不再裸调用
- **Session 管理**：支持 OpenClaw 会话 ID 到 claude-node session 的映射，支持 resume/continue
- **事件流返回**：将 assistant/tool_result/task_progress 等中间事件通过 OpenClaw 的 WebSocket 推送回 Feishu（而非只等 result）
- **工具链配置**：默认启用完整工具集（Bash/Read/Write/Glob/Grep/WebFetch/MCP tools）
- **错误处理增强**：区分 API 错误 vs 工具执行失败 vs 进程异常
- **启动预检**：Gateway 启动时检查 claude binary 可用性，避免运行时才发现

## Capabilities

### New Capabilities

- `wrapper-session-management`: OpenClaw 会话 ID ↔ claude-node session 映射管理，支持 resume/fork
- `wrapper-event-streaming`: 将 stream-json 中间事件（assistant/tool_result/task_progress）推送回 OpenClaw
- `wrapper-config-driven`: 所有运行时参数（cwd、tools、model、permission-mode）通过环境变量配置
- `wrapper-error-classification`: 错误分类（API error / tool failure / process error）及结构化返回

## Impact

- `/Users/c/claude-node-cli-wrapper.py` — 完全重写
- `~/.openclaw/openclaw.json` — cliBackends.env 增加配置项
- OpenClaw Gateway — 需支持接收 streaming 事件（若当前不支持则标注为 open question）
