## Why

当前 clawrelay-report 的会话页面采用 `/sessions` 列表 + `/sessions/:id` 详情两页式设计，工具调用状态混在对话历史中导致信息密度过高、难以阅读。用户需要的是一个独立的 Chat 页面，同时展示对话和 AI 工具执行状态，支持会话切换和会话重命名。

## What Changes

- **新增独立 Chat 页面** (`/chat`)，替换现有的两页式设计
- **三栏布局**：左侧工具栏（现有侧边栏）+ 中间会话历史 + 右侧工具执行状态面板（可折叠）
- **顶部会话选择器**：下拉菜单选择当前会话，内含"新建会话"入口
- **Admin 重命名**：会话列表悬停显示编辑图标，点击弹出 Input 框重命名
- **实时工具状态**：基于 `stream_chat()` 的 `ToolUseStart` 事件，实时显示工具调用时间线
- **普通用户**：只能看到自己创建的会话；Admin：可以看到所有会话并重命名

## Capabilities

### New Capabilities

- `session-selector`: 顶部会话选择器，支持下拉切换会话、创建新会话、Admin 重命名
- `tool-status-panel`: 右侧工具执行状态面板，实时展示 AI 调用工具的时间线，支持折叠
- `chat-page`: 新的独立 Chat 页面，整合会话历史和工具状态
- `session-access-control`: 会话访问控制，普通用户只能看到自己的会话，Admin 可以看到并管理所有会话

### Modified Capabilities

- 无（现有 spec 目录为空）

## Impact

- **新增页面路由**: `/chat` (TanStack Router)
- **修改页面**: 删除或保留现有的 `/sessions` 列表页和 `/sessions/:id` 详情页（待定）
- **新增 API**: Admin 重命名会话端点（如果后端尚无）
- **WebSocket 事件**: 复用现有的 `delta`/`done`/`error` 事件
- **前端组件**: 新增 `ToolStatusPanel`、`SessionSelector` 组件
