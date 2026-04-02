## 1. Model 统一成 MINIMAX

- [x] 1.1 读取当前 `~/.openclaw/openclaw.json` 配置
- [x] 1.2 将 `agents.defaults.model.primary` 从 `claude-node-cli/claude-sonnet-4-6` 改为 `minimax-cn/MiniMax-M2.7`
- [x] 1.3 保留 `fallbacks` 数组中的 `minimax-cn/MiniMax-M2.7` 作为后备
- [x] 1.4 重启 OpenClaw Gateway 使配置生效
- [x] 1.5 验证模型切换：发送测试消息，确认日志中显示 minimax 模型

## 2. Hook 脚本路径错误清理

- [x] 2.1 读取当前 `~/.claude/settings.local.json` 配置
- [x] 2.2 删除 `hooks.SessionStart` 数组中指向以下路径的配置：
  - `/Users/c/.claude/plugins/branch-autonomous/hooks/session-start.sh` (目录不存在)
  - `ECC_STATE_DIR=$HOME/.claude/superpowers-ecc node $CLAUDE_PLUGIN_ROOT/hooks/scripts/instincts-inject.js` (模块不存在)
- [x] 2.3 验证 `hooks.SessionStart` 数组为空或只包含有效配置
- [x] 2.4 测试会话启动不再报 `unbound variable` 或 `module not found` 错误
