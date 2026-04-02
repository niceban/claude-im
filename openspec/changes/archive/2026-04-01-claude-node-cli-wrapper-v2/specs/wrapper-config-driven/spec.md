## Capability: wrapper-config-driven

### Requirement: 所有运行时参数通过环境变量配置

wrapper.py 不硬编码任何路径、工具列表或模型参数，全部从环境变量读取。

### 环境变量清单

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `CLAUDE_NODE_PATH` | `/private/tmp/claude-node` | claude-node 包路径 |
| `CLAUDE_CWD` | `/Users/c` | 工作目录 |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | 模型名称 |
| `CLAUDE_TOOLS` | `Bash,Read,Write,Glob,Grep,WebFetch,Agent,Task,TaskOutput,TodoWrite,Edit,Search` | 工具白名单 |
| `CLAUDE_SKIP_PERMISSIONS` | `true` | 跳过权限确认 |
| `CLAUDE_PERMISSION_MODE` | ` ` | 权限模式（acceptErrors / intelligent/HAI） |
| `CLAUDE_ADD_DIRS` | `` | 额外上下文目录（逗号分隔） |
| `CLAUDE_SESSION_MAP_FILE` | `~/.claude/sessions.json` | session 映射文件 |
| `CLAUDE_STREAM_EVENTS` | `true` | 是否启用事件流 |
| `CLAUDE_TIMEOUT` | `300` | 默认超时（秒） |
| `CLAUDE_TRANSCRIPT_DIR` | `~/.claude/transcripts` | transcript 输出目录 |

### 验证逻辑

启动时检查：
1. `CLAUDE_NODE_PATH` 是否存在且包含 `claude_node` 模块
2. `CLAUDE_CWD` 是否是有效目录
3. `claude` binary 是否在 PATH 中

### Scenario: 默认配置
- **WHEN** wrapper 启动且所有环境变量使用默认值
- **THEN** 使用上表默认值运行

### Scenario: 自定义配置
- **WHEN** openclaw.json 中 cliBackends.env 设置了自定义值
- **THEN** 环境变量值覆盖默认值

### Scenario: 配置缺失
- **WHEN** `CLAUDE_TOOLS` 未设置
- **THEN** 使用默认工具列表（不报错）

### Boundary

- 所有路径类变量支持相对路径（相对于 `CLAUDE_CWD`）
- 工具列表为空时不启动 claude-node，返回配置错误
