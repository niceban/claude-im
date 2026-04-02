## Why

Team review 发现 `settings.local.json` 中有 7 个损坏的 hook 脚本路径（branch-autonomous 插件已卸载但 hook 配置仍活跃），每次 Bash/Stop/UserPromptSubmit 事件都会触发破碎命令。同时 `openclaw.json` 的 fallback 路径有两个 HIGH 问题导致 fallback 会静默失败。

## What Changes

**Phase 1 — Hook 清理（CRITICAL × 2）：**
1. 删除 `settings.local.json` 中所有 `branch-autonomous` 引用（6 个破碎脚本）
2. 删除 `settings.local.json` 中 `deep-now-autoprompt` 引用（skill 不存在）

**Phase 2 — Fallback 修复（HIGH × 2）：**
3. 修复 `CLAUDE_MODEL` 为裸模型名 `MiniMax-M2.7`（去掉 provider 前缀）
4. cliBackends env 中添加 `MINIMAX_API_KEY` 和 `MINIMAX_BASE_URL`

## Capabilities

### Modified Capabilities

- `claude-code-hooks`: 删除所有破碎路径的 hook 引用
- `claude-im-runtime`: 修复 fallback 路径使 MiniMax fallback 实际可用

## Impact

- 修改文件：`~/.claude/settings.local.json`、`~/.openclaw/openclaw.json`
- 无 API 变更
- 无 Breaking Changes
- 消除每次交互时的破碎 hook 错误日志
