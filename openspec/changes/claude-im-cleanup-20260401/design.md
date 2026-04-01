## Context

当前 claude-im 项目已通过 CLI Backend 方案成功运行（2026-04-01 验证）。但存在以下维护问题：

1. `CLAUDE.md` 描述的是旧架构（clawrelay-feishu-server），与实际运行架构不符
2. `openclaw-claude-bridge/` 插件注册了 `input:stdin` 的 Backend，但实际使用的是 `cliBackends` 配置里 `input:arg` 的 Backend——插件代码是死代码
3. `/private/tmp/claude-node` 硬编码在 wrapper.py 里，应改为更可靠的引用方式
4. `openclaw-claude-bridge/` 下有未提交的开发文件（docs、tests、src/claude_node/ 副本）
5. `openspec/changes/document-current-project-issues/` 已完成但未归档

## Goals / Non-Goals

**Goals:**
- 让 CLAUDE.md 与实际架构一致，消除对后续维护者的误导
- 清理死代码和开发残留，减少技术债务
- 解决 wrapper 路径硬编码问题，提高可维护性

**Non-Goals:**
- 不改变当前运行的架构（Gateway + CLI Backend 已经工作）
- 不做功能开发或性能优化
- 不修改 openclaw.json 配置（当前配置已验证可用）

## Decisions

**1. CLAUDE.md 架构更新**
- 替换旧架构描述（clawrelay-feishu-server → claude-node）为实际架构（OpenClaw Gateway → wrapper.py → claude-node → Claude CLI）
- 保留旧架构的对比说明，标注"已废弃"

**2. openclaw-claude-bridge 插件死代码清理**

现状：
- 插件被加载（`/Users/c/.openclaw/extensions/openclaw-claude-bridge/index.js`）
- 插件注册的 Backend 使用 `input:stdin`（从未被使用）
- 实际工作的 Backend 定义在 `openclaw.json` 的 `cliBackends` 配置中

方案：删除插件中从未被调用的 backend 注册代码，保留插件结构（因为 `plugins.entries` 里已声明）或直接删除整个插件（因为 `cliBackends` 配置不依赖插件）

**选择**：删除整个 `openclaw-claude-bridge` 插件——`cliBackends` 配置不依赖插件存在，插件对运行无实际贡献

**3. wrapper 路径问题**

现状：`CLAUDE_NODE_PATH = '/private/tmp/claude-node'` 硬编码在 wrapper.py

方案：
- 方案A：改为 pip install 的包，通过 `import claude_node` 使用（最干净）
- 方案B：通过环境变量配置路径

**选择**：方案A（pip install），因为 `/private/tmp` 是临时目录，重启可能丢失

**4. 未提交文件整理**

保留：`test_cli_backend_e2e.py`（有价值的 E2E 测试）、`docs/`（如果内容有价值）
删除：`src/claude_node/` 副本（应通过 pip install）、`package.json`/`package-lock.json`（npm 依赖从未被使用）、tsconfig.json

**5. OpenSpec 归档**

将 `document-current-project-issues/` 移动到 archive/

## Risks / Trade-offs

- [风险] 删除插件后，如果将来需要通过插件机制扩展功能，代码已不存在 → **缓解**：当前 `cliBackends` 配置已足够，插件机制文档在 git 历史中可恢复
- [风险] pip install claude-node 如果版本与 `/private/tmp/claude-node` 不同步 → **缓解**：先验证 pip 版本与当前使用的接口兼容

## Open Questions

1. `/private/tmp/claude-node` 的来源是什么？是 git clone 还是 pip install 的缓存？这个路径本身是否稳定？
2. `test_cli_backend_e2e.py` 是否真的在测试当前运行配置（`input:arg`）？还是测试的旧 `input:stdin` 配置？
