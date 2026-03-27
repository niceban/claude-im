# Deep-Now Cycle 001

## Problem
1. 把最新结论写入文档
2. 验证 `Agent()` tool 和多工具组合是否真的因 401 auth 失败

## 结论（已验证）

**所有能力均正常工作：**

| 能力 | 状态 | 备注 |
|------|------|------|
| MCP 工具 (web_search) | ✅ | MINIMAX_API_KEY 认证 |
| /deep-now | ✅ | 单 agent 内循环 |
| Agent() tool (直接 CLI) | ✅ | 实测返回 PASS |
| Agent() tool (feishu adapter) | ✅ | 实测返回 PASS，Token 消耗 25207 |
| 多工具组合 | ✅ | 实测正常 |
| 直接 API 调用 (无 proxy) | ✅ | Status 200 |

**之前 401 报错的原因（分析）：**
1. curl 测试缺少 `anthropic-version` header，误导判断
2. 测试脚本用了错误的 flag `--skip-permissions`（正确是 `--dangerously-skip-permissions`）
3. `.env` 文件可能在某段时间有错误 token，已被修复

## Bot 架构（当前正常状态）

```
launchd 进程 (clawrelay-feishu-server)
└── Python 进程 (main.py) + load_dotenv
    └── ClaudeController (claude-node subprocess)
        └── Claude Code CLI subprocess
            ├── ANTHROPIC_AUTH_TOKEN ✅ (125字符，与shell一致)
            ├── ANTHROPIC_BASE_URL ✅
            ├── MCP MiniMax ✅ (MINIMAX_API_KEY)
            ├── Agent() tool ✅
            └── 多工具组合 ✅
```

## 验证记录

### 直接 CLI 测试
```bash
claude --print '用 Agent() tool 启动子 agent，让它回复 PASS'
# 结果: 子 agent 回复结果：**PASS** ✅
```

### feishu adapter 测试
```python
# 通过 claude_node_adapter 完整调用链测试
result = await orch.handle_text_message(
    message='请用 Agent() tool 启动一个子 agent，让它回复 PASS'
)
# 结果: 子 Agent 执行完毕，回复结果：**PASS**
# Agent ID: ac0fe05066e94d5d4
# Token 消耗: 25207 ✅
```

### API 直接调用（无 proxy）
```python
# 清除所有 proxy 环境变量后直接调用 MiniMax API
urllib.request.urlopen('https://api.minimaxi.com/anthropic/v1/messages', ...)
# 结果: Status 200 ✅（不需要 proxy）
```

## 关键发现

### token 验证
- `.env` token (125字符) == Shell token (125字符) == MCP config token
- 所有 token 完全一致，无差异
- `load_dotenv(override=False)` 正确加载

### proxy 环境变量
- launchd plist 清理了所有 proxy 变量（http_proxy 等设为空字符串）
- 但 MiniMax API 无需 proxy 即可直接访问（直接连接返回 200）

### subprocess 启动验证
- 使用 `--dangerously-skip-permissions` + `--verbose` + `--input-format stream-json --output-format stream-json` 可以正常启动
- 错误 flag `--skip-permissions` 会导致 subprocess 立即退出（exit=1, stderr: unknown option）

## Files
- `/Users/c/clawrelay-feishu-server/src/adapters/claude_node_adapter.py`
- `/private/tmp/claude-node/claude_node/controller.py`
- `/Users/c/clawrelay-feishu-server/src/core/claude_relay_orchestrator.py`
- `/Users/c/clawrelay-feishu-server/config/bots.yaml`
- `/Users/c/clawrelay-feishu-server/.env`
- `~/.claude/.claude.json` — MCP server 配置
