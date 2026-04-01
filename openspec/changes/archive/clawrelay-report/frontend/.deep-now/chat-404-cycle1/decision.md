# Decide + Execute: TanStack Router /chat 404

## 根因

`/Users/c/claude-im/clawrelay-report/node_modules/.bin/vite` 中的路径引用错误：
- 错误：`import('../dist/node/cli.js')` → `/node_modules/dist/node/cli.js`（不存在）
- 正确：`import('../vite/dist/node/cli.js')` → `/node_modules/vite/dist/node/cli.js`

## Execute 步骤

1. `pkill -f vite` — 停止所有 vite 进程
2. 修复 `node_modules/.bin/vite` 第 62 行路径
3. `rm -f frontend/src/routeTree.gen.ts` — 删除旧的手动编辑文件
4. `bun run --filter frontend dev` — 重启 dev server
5. 插件自动扫描 `chat.tsx` 并重新生成 `routeTree.gen.ts`

## 结果

- `routeTree.gen.ts` 被正确生成，包含完整的 `/chat` 路由
- Vite dev server 在 localhost:5173 正常运行
- `/chat` 页面应可正常访问
