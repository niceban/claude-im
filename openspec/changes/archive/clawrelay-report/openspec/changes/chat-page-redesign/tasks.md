## 1. Backend: Admin 重命名 API

- [x] 1.1 确认 `PATCH /api/v1/admin/sessions/{relay_session_id}` 端点是否已存在
- [x] 1.2 如果不存在，在 `clawrelay-feishu-server/src/admin/routes.py` 中实现该端点
- [x] 1.3 如果不存在，在 `clawrelay-report/backend/app/api/routes/metrics.py` 中添加对应的代理端点
- [ ] 1.4 测试 Admin 重命名 API

## 2. Frontend: 新增 Chat 页面路由

- [x] 2.1 在 `clawrelay-report/frontend/src/routes/` 下创建 `/_layout/chat.tsx` 页面文件
- [x] 2.2 在 TanStack Router 中注册 `/chat` 路由（TanStack 文件路由自动注册）
- [x] 2.3 在侧边栏 `AppSidebar.tsx` 中添加 "Chat" 导航入口（指向 `/chat`）

## 3. Frontend: 顶部会话选择器组件

- [x] 3.1 创建 `SessionSelector` 组件（基于 shadcn/ui Select 组件） - 已集成在 chat.tsx
- [x] 3.2 实现会话列表下拉（显示 session ID 截断 + 最后活跃时间）
- [x] 3.3 实现悬停显示编辑图标，Admin 点击弹出 Input 框重命名
- [x] 3.4 实现"创建新会话"入口（调用 `POST /api/v1/chat/sessions`）
- [x] 3.5 实现切换会话时清空并重新加载右侧工具状态

## 4. Frontend: 工具状态面板组件

- [x] 4.1 创建 `ToolStatusPanel` 组件 - 已在 chat.tsx 中实现
- [ ] 4.2 实现 `ToolUseStart` 事件的监听和实时显示（需要 WS 协议扩展）
- [ ] 4.3 实现 `done` 事件后更新工具状态为"完成"（✓） - 待 WS 协议支持
- [x] 4.4 实现折叠/展开按钮（−/+）
- [ ] 4.5 实现按消息分组显示工具调用

## 5. Frontend: 会话历史区域组件

- [x] 5.1 提取/复用 `$sessionId.tsx` 中的对话展示逻辑到 `ConversationView` 组件
- [x] 5.2 实现 WebSocket 连接管理（`delta`/`done`/`error` 事件处理）
- [x] 5.3 实现消息输入区域（支持 Enter 发送和 Shift+Enter 换行）
- [x] 5.4 实现空状态引导（无会话时显示"创建新会话"提示）
- [x] 5.5 实现乐观 UI（发送消息后立即显示）

## 6. Frontend: 布局集成

- [x] 6.1 在 `chat.tsx` 中组装三栏布局（侧边栏 + 会话历史 + 工具状态面板）
- [ ] 6.2 确保布局响应式（移动端面板可折叠）
- [x] 6.3 连接会话选择器到 ConversationView（切换会话时更新显示）

## 7. Frontend: 访问控制

- [x] 7.1 确认会话列表 API 支持 `owner_id` 过滤（普通用户只看到自己的） - metrics.py:202-203
- [x] 7.2 确认 Admin 可以获取所有会话 - metrics.py:201
- [x] 7.3 隐藏/禁用非 Admin 用户的重命名功能 - chat.tsx 中已实现

## 8. 测试与验证

- [ ] 8.1 手动测试：创建新会话 → 发送消息 → 查看右侧工具状态
- [ ] 8.2 手动测试：切换会话 → 确认右侧面板重置
- [ ] 8.3 手动测试：折叠/展开右侧面板
- [ ] 8.4 手动测试：Admin 重命名会话
- [ ] 8.5 手动测试：非 Admin 用户无法重命名单他人的会话
- [ ] 8.6 确认 WebSocket 重连机制（onclose/onerror）
