# 变更记录

## 2026-03-24 — 初始化部署

### 部署环境
- macOS (Darwin 25.3.0)
- Go 1.26.0
- Python 3.12.7
- Node.js 25.2.1
- Claude Code CLI v2.1.81

### 部署组件
| 组件 | 版本 | 仓库 |
|------|------|------|
| clawrelay-api | latest | roodkcab/clawrelay-api |
| clawrelay-feishu-server | v1.0.0 | wxkingstar/clawrelay-feishu-server |
| Claude Code CLI | 2.1.81 | anthropic-ai/claude-code |

### 飞书 Bot 配置
- App ID: `cli_a925d01967791cd5`
- 连接模式: WebSocket 长连接
- 权限: im:message, im:message.group_at_msg, im:resource
- 事件: im.message.receive_v1

### 架构路径
```
飞书用户 → feishu-server (Python asyncio WebSocket)
        → clawrelay-api (Go :50009, OpenAI 兼容 API)
        → claude CLI (真正执行内核)
```

### 清理记录
- nanoclaw IM 相关进程已清理
- nanoclaw docker 镜像已删除
- nanoclaw 目录已删除

### 待优化项
- [ ] 多 Bot 支持
- [ ] 会话压缩策略
- [ ] 外置会话存储 (Redis)
- [ ] 监控告警
- [ ] 企业微信适配器

---

## 架构决策记录 (ADR)

### ADR-001: 选择 clawrelay 系列而非自研
**决定**: 使用 clawrelay-api + clawrelay-feishu-server 作为基础
**原因**:
- 开源成熟，已产品化
- WebSocket 长连接，无需公网 IP/回调
- OpenAI 兼容 API，易扩展
- 社区活跃，issue 响应快

**替代方案考虑**:
- Claude-to-IM: 需要自行实现 ~30 个存储方法
- Gobby: 架构较重，适合多 CLI 编排
- 自研 glue code: 维护成本高

### ADR-001b: claude-node vs clawrelay-api 认知修正
**日期**: 2026-03-24
**修正**: 之前错误地认为 claude-node 是封装 Claude HTTP API 的 Node.js SDK，实际上：
- claude-node 是 **Python 库**，封装的是 `claude` **CLI 子进程**（和 clawrelay-api 做相同的事）
- claude-node spawns `claude --input-format stream-json --output-format stream-json`
- 唯一区别：clawrelay-api 是 Go HTTP 服务；claude-node 是 Python 库
- 两者都可以作为 IM 适配层的底层

---

## 2026-03-24 — 文档更新（认知修正）

### 修正内容
- **CLAUDE.md**: 修正 claude-node 认知（原错误描述为"封装 Claude HTTP API"）
- **EXTENSION.md**: 新增「用 claude-node 替代 clawrelay-api」章节

### claude-node 关键信息
- 仓库: https://github.com/claw-army/claude-node
- 启动命令: `claude --input-format stream-json --output-format stream-json --verbose`
- 核心类: `ClaudeController`（上下文管理器）、`ClaudeMessage`（消息解析）、`MultiAgentRouter`（多会话路由）
- 会话管理: `resume=<session_id>`, `fork()`, `continue_session=True`
- 工具调用: `msg.tool_calls`, `msg.tool_results`, `msg.get_tool_errors()`

### ADR-002: Claude CLI bypassPermissions 模式
**决定**: 使用 `--permission-mode bypassPermissions`
**原因**: IM 平台场景下无法进行交互式审批
**风险**: 任意合法用户可触发工具执行 → 通过 `allowed_users` 白名单缓解

### ADR-003: 会话存储方案
**决定**: 使用 clawrelay-api 内置 JSONL 文件存储
**原因**: 零外部依赖，足够轻量
**未来**: 可扩展为 Redis 外置存储以支持分布式部署
