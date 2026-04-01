## Context

**现状**：clawrelay-report 的会话功能分散在两个页面：
- `/sessions` — 会话列表（表格形式，支持筛选、分页）
- `/sessions/:id` — 会话详情（5个统计卡片 + 对话历史 + 输入框）

**痛点**：
- 工具调用状态（如 `Bash: touch app.py`）混在对话气泡中，信息密度高
- 会话切换需要返回列表页再进入详情页，路径长
- 无法实时监控工具执行状态

**技术约束**：
- 前端框架：React + TanStack Router + TanStack Query
- UI 组件库：shadcn/ui
- 后端：FastAPI（clawrelay-report）代理到 clawrelay-feishu-server (8088)
- 实时通信：WebSocket（现有 `delta`/`done`/`error` 事件）
- 工具状态数据来源：`stream_chat()` 的 `ToolUseStart` 事件（实时），`tools_used` 字段（事后，仅工具名列表）

## Goals / Non-Goals

**Goals:**
- 独立的 Chat 页面，同时展示对话历史和工具执行状态
- 顶部会话选择器下拉，支持快速切换会话
- 右侧工具状态面板可折叠，节省空间
- 普通用户只能看到自己的会话，Admin 可看到并重命名所有会话
- Admin 可在会话列表悬停时重命名会话

**Non-Goals:**
- 不做实时工具输出（如 stdout/stderr 流式展示），仅显示工具名称 + 执行状态
- 不修改现有的 WebSocket 协议
- 不改变 JSONL 持久化格式

## Decisions

### Decision 1: 新页面路由 `/chat`

**选择**：新增 `/chat` 页面，替代现有的 `/sessions` 和 `/sessions/:id`。

**替代方案**：
- 直接改造现有 `/sessions/:id` — 会丢失列表页的筛选/分页能力
- 两个页面并行存在 — 维护两套逻辑，增加复杂度

### Decision 2: 工具状态数据来源

**选择**：以 `ToolUseStart` 事件为实时数据源，`tools_used` 为历史补充。

```
用户发送消息
  → stream_chat() 开始流式响应
  → ToolUseStart(name="Bash") 事件 → 立即显示在右侧面板
  → ToolUseStart(name="Edit") 事件 → 追加到右侧面板
  → done 事件 → 最终 tools_used 补充到面板
```

**替代方案**：
- 仅用 `tools_used` — 非实时，必须等消息处理完才有显示
- 接入 ClaudeController 的 stdout/stderr — 复杂度高，后续迭代

### Decision 3: 工具状态面板折叠方式

**选择**：右侧面板内，左上角放置 `−` 图标按钮，点击折叠/展开。

**替代方案**：
- 拖动分割线调整宽度 — 增加实现复杂度
- 右滑 Sheet 抽屉 — 不符合"常驻监控"的使用场景

### Decision 4: Admin 重命名交互

**选择**：会话选择器下拉中，悬停项显示 ✏️ 图标，点击弹出 Input 框编辑名称。

**替代方案**：
- 右键菜单 — 需要额外实现 context menu
- 列表页单独管理 — 增加操作路径

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| `ToolUseStart` 事件不含执行结果，无法确认工具是否成功 | 结合 `done` 事件的 `tools_used` 作为最终状态 |
| 切换会话时右侧面板状态需要重置 | 会话切换时清空工具状态，重新开始累计 |
| Admin 重命名需要后端 API 支持 | 如果尚无，实现一个 `PATCH /admin/sessions/{id}` 端点 |

## Migration Plan

1. 新增 `/chat` 路由页面（独立于现有页面）
2. 侧边栏导航添加 "Chat" 入口
3. 后端（如需要）新增 Admin 重命名 API
4. 验证功能后，将旧的 `/sessions` 和 `/sessions/:id` 标记为废弃或删除
5. 前端清理相关路由和组件

## Open Questions

1. 旧的 `/sessions` 列表页是否保留？（如果保留，Chat 页的会话列表是否与之合并？）
2. 会话"名称"存储在哪里？（目前只有 `relay_session_id`，需要确认是否需要新增 `name` 字段）
