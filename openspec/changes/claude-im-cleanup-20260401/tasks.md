## 1. CLAUDE.md Architecture Update

- [x] 1.1 Read current CLAUDE.md architecture section
- [x] 1.2 Rewrite architecture description to reflect: OpenClaw Gateway → cliBackends → wrapper.py → claude-node → Claude Code CLI
- [x] 1.3 Add "Previous Architecture" section marking clawrelay-feishu-server as deprecated

## 2. openclaw-claude-bridge Plugin Cleanup

- [x] 2.1 Verify `cliBackends` works WITHOUT the plugin (delete plugin from `~/.openclaw/extensions/` and restart gateway)
- [x] 2.2 If CLI still works without plugin, remove plugin from `~/.openclaw/openclaw.json` plugins.entries and plugins.allow
- [x] 2.3 Delete `openclaw-claude-bridge/` plugin source directory (dead code)

## 3. wrapper.py Path Fix

- [x] 3.1 Check if `claude-node` is available via pip install
- [x] 3.2 If pip version available and compatible, update wrapper.py to `import claude_node` instead of hardcoded path
- [x] 3.3 If pip version not suitable, use environment variable for path instead of hardcode
- [x] 3.4 Test wrapper still works after path change

## 4. Uncommitted Files in openclaw-claude-bridge/

- [x] 4.1 Review uncommitted files: `docs/`, `src/claude_node/`, `test_cli_backend_e2e.py`
- [x] 4.2 Keep:有价值 docs 和 test_cli_backend_e2e.py（如果测试的是当前 input:arg 配置）
- [x] 4.3 Delete: `src/claude_node/` 副本（改用 pip install）、npm 相关文件（从未使用）
- [x] 4.4 Commit clean state

## 5. OpenSpec Archive

- [x] 5.1 Move `openspec/changes/document-current-project-issues/` to archive/
- [x] 5.2 Commit archive change
