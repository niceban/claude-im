# Scout Findings: TanStack Router /chat 404

## 根因假设（按可能性排序）

### H1（最高）：Dev server 使用了旧的/被覆盖的 routeTree.gen.ts
- Vite 插件在启动时生成 `routeTree.gen.ts`
- 如果 dev server 在 `chat.tsx` 创建之前就已启动，插件可能未扫描到新文件
- 手动编辑的 `routeTree.gen.ts` 会在 dev server 重启时被插件覆盖

### H2（中）：Vite 插件版本不匹配
- @tanstack/router-plugin: 1.153.2
- @tanstack/react-router: 1.163.3
- 相差约 10 个 minor 版本

### H3（中）：路由文件命名/位置不符合约定
- `chat.tsx` 放在 `src/routes/_layout/chat.tsx`
- `_layout.tsx` 是 parent route
- 需要确认这个结构是否被插件正确识别

## 事实链条

1. `src/routes/_layout/chat.tsx` — Untracked（新文件，从未提交）
2. `src/routeTree.gen.ts` — Modified（手动添加了 5 处 chat 相关变更，但这些变更在 dev server 重启后会被插件覆盖）
3. `sessions/index.tsx` 和 `sessions/$sessionId.tsx` 正常工作 — 说明插件本身能扫描 `_layout/` 下的子目录
4. Vite 插件配置无 `routesFolder` 显式配置

## 最可能根因

**Dev server 没有重启，或者插件在启动时生成了不包含 chat 路由的 routeTree.gen.ts，而手动编辑的文件在后续重启中被覆盖。**

## 验证步骤

1. 停止 dev server：`pkill -f vite`
2. 删除手动编辑的 `routeTree.gen.ts`
3. 重新 `npm run dev` — 让插件完整重新扫描所有路由文件
4. 访问 `/chat` 测试
