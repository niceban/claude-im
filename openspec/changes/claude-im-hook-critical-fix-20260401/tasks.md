## Phase 1: Hook 清理（CRITICAL 修复）

- [x] 1.1 读取当前 `~/.claude/settings.local.json`
- [x] 1.2 删除 `UserPromptSubmit[0]` 中的 `deep-now-autoprompt` hook 条目
- [x] 1.3 删除 `UserPromptSubmit[0]` 中的 `branch-autonomous/semantic-trigger.sh` hook 条目
- [x] 1.4 删除 `PreToolUse` 中所有 `branch-autonomous` hook 条目（guard-bash.sh, pre-push.sh）
- [x] 1.5 删除 `PostToolUse` 中 `branch-autonomous/hooks/post-tool.sh` 条目
- [x] 1.6 删除 `PostToolUseFailure` 中 `branch-autonomous/hooks/post-tool-fail.sh` 条目
- [x] 1.7 删除 `Stop[0]` 中 `branch-autonomous/hooks/stop.sh` 条目
- [x] 1.8 验证清理后 JSON 有效（无残留 branch-autonomous/deep-now-autoprompt）

## Phase 2: Fallback 路径修复（HIGH 修复）

- [x] 2.1 读取当前 `~/.openclaw/openclaw.json`
- [x] 2.2 将 `cliBackends.claude-node-cli.env.CLAUDE_MODEL` 从 `minimax-cn/MiniMax-M2.7` 改为 `MiniMax-M2.7`
- [x] 2.3 在 `cliBackends.claude-node-cli.env` 中添加 `MINIMAX_API_KEY` 和 `MINIMAX_BASE_URL`
- [x] 2.4 重启 OpenClaw Gateway 使配置生效
- [x] 2.5 验证配置正确：Gateway 日志显示 `agent model: minimax-cn/MiniMax-M2.7`，4 个内部 hooks 加载成功
