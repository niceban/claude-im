## Why

项目已通过 CLI Backend 方案成功接入飞书，但 CLAUDE.md 文档仍描述旧架构，且存在多处未同步的技术债务：文档过时、插件代码半死、wrapper 路径硬编码、散落的未提交开发文件。这些问题影响长期维护。

## What Changes

1. **更新 CLAUDE.md** — 替换旧架构描述为实际运行的 OpenClaw Gateway + CLI Backend 架构
2. **整理 openclaw-claude-bridge 未提交文件** — 将 docs、tests、src/claude_node/ 副本等开发残留整理或删除
3. **修复或移除死代码** — 插件中 `input:stdin` 的 backend 注册从未被使用，需清理
4. **解决 wrapper 硬编码路径** — `/private/tmp/claude-node` 应改为 pip install 或相对路径
5. **归档 document-current-project-issues OpenSpec** — 该 spec 任务已全部完成，可归档

## Capabilities

### New Capabilities

- `claude-im-runtime-docs`: 更新后的 CLAUDE.md 文档，描述当前实际运行的 OpenClaw Gateway + CLI Backend 架构

### Modified Capabilities

（无 spec 级别变更，本次为维护性工作）

## Impact

- 影响的文件：`CLAUDE.md`、`openclaw-claude-bridge/` 下未跟踪的开发文件
- 无 API 变更
- 无 Breaking Changes
