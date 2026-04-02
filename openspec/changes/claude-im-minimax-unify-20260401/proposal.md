## Why

当前 OpenClaw Gateway 的 primary model 配置为 `claude-node-cli/claude-sonnet-4-6`，但用户要求统一使用 MINIMAX 模型。同时 `settings.local.json` 中存在两个损坏的 SessionStart hook，指向不存在的路径，导致每次会话启动时抛出错误。

## What Changes

1. **Model 统一** — 修改 `~/.openclaw/openclaw.json`，将 `agents.defaults.model.primary` 从 `claude-node-cli/claude-sonnet-4-6` 改为 `minimax-cn/MiniMax-M2.7`
2. **Hook 清理** — 从 `~/.claude/settings.local.json` 中删除两个损坏的 SessionStart hook 配置
   - `branch-autonomous/hooks/session-start.sh` (路径不存在)
   - `instincts-inject.js` (模块不存在)

## Capabilities

### Modified Capabilities

- `claude-im-runtime`: OpenClaw Gateway 模型配置，primary model 改为 minimax
- `claude-code-hooks`: 清理损坏的 hook 配置，消除启动错误

## Impact

- 修改文件：`~/.openclaw/openclaw.json`、`~/.claude/settings.local.json`
- 无 API 变更
- 无 Breaking Changes
- Hook 错误消除
