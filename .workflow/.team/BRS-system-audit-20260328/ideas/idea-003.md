# 审计发现：STANDARD.md 描述与实际代码一致性

## 审计任务
验证 `STANDARD.md` 描述的架构是否与实际代码匹配。

---

## 1. IM 执行链路验证

### STANDARD.md 描述
```
Feishu / WeCom
  -> clawrelay-feishu-server / clawrelay-wecom-server
  -> claude-node
  -> Claude Code CLI
```

### 实际代码验证

| 验证项 | 状态 | 证据 |
|--------|------|------|
| `clawrelay-feishu-server` 存在 | MATCH | `/Users/c/clawrelay-feishu-server` 目录存在 |
| `claude-node` 存在 | MATCH | `/Users/c/claude-node` 目录存在 |
| `clawrelay-feishu-server` 调用 `claude-node` | MATCH | `src/adapters/claude_node_adapter.py:19` - `from claude_node import ClaudeController, ClaudeMessage` |
| `ClaudeNodeAdapter` 实现正确 | MATCH | 直接驱动 Claude Code CLI 子进程，通过 `stdin/stdout stream-json` 双向通信 |

### 详细证据

**文件**: `/Users/c/clawrelay-feishu-server/src/adapters/claude_node_adapter.py`
```python
from claude_node import ClaudeController, ClaudeMessage  # Line 19

class ClaudeNodeAdapter:
    """
    直接 import claude-node 的适配器。
    直接驱动 Claude Code CLI 子进程，通过 stdin/stdout stream-json 双向通信，无需 HTTP 服务
    """
```

---

## 2. 报表系统验证

### STANDARD.md 描述
```
clawrelay-feishu-server
  -> clawrelay-report backend
  -> clawrelay-report frontend
```

**唯一管理后台入口**: `http://localhost:5173`

### 实际代码验证

| 验证项 | 状态 | 证据 |
|--------|------|------|
| `clawrelay-report` 存在 | MATCH | `/Users/c/clawrelay-report` 目录存在 |
| 有完整 backend | MATCH | `/Users/c/clawrelay-report/backend/` 目录存在，包含 FastAPI 后端 |
| 有完整 frontend | MATCH | `/Users/c/clawrelay-report/frontend/` 目录存在，包含 React 前端 |
| 5173 是唯一入口 | MATCH | `development.md:18` - "前端入口固定为 `http://localhost:5173`" |

### 详细证据

**compose.override.yml:99**
```yaml
- "5173:80"  # 5173 映射到 nginx 80 端口
```

**clawrelay-report/README.md:7**
```
- 管理后台入口：`http://localhost:5173`
```

**clawrelay-report/README.md:32**
```
- 唯一管理后台入口是 `http://localhost:5173`
```

**clawrelay-report/frontend/README.md:19**
```
- `5173` 是唯一对人入口
```

---

## 3. 禁止路径验证 (clawrelay-api)

### STANDARD.md 描述
```
`clawrelay-api` **不再属于标准架构**
```
```
- `clawrelay-api` 与 `claude-node` 双路线并存 → 废弃
- 用 `clawrelay-api` 作为当前主运行链路 → 废弃
```

### 实际代码验证

| 验证项 | 状态 | 证据 |
|--------|------|------|
| `clawrelay-api` 在 `clawrelay-feishu-server` 中无引用 | MATCH | `grep "clawrelay-api" /Users/c/clawrelay-feishu-server` → No matches found |
| `clawrelay-api` 在 `clawrelay-report` 中无引用 | MATCH | `grep "clawrelay-api" /Users/c/clawrelay-report` → No matches found |
| `clawrelay-api` 在 `STANDARD.md` 中正确标记为废弃 | MATCH | Line 21: "`clawrelay-api` **不再属于标准架构**" |

### `clawrelay-api` 仅存于正确位置

| 位置 | 内容 | 是否正确 |
|------|------|----------|
| `STANDARD.md:21` | "`clawrelay-api` **不再属于标准架构**" | 正确（废弃声明） |
| `AGENTS.md:8` | "`clawrelay-api` **不再属于标准架构**" | 正确（约束说明） |
| `AGENTS.md:16` | "不得把 `clawrelay-api` 重新写回文档、脚本、架构总结" | 正确（禁止性约束） |

---

## 审计结论

| 检查项 | STANDARD.md 描述 | 实际代码 | 一致性 |
|--------|------------------|----------|--------|
| IM 执行链路 | `clawrelay-feishu-server -> claude-node -> Claude Code CLI` | `claude_node_adapter.py` 直接 import `claude_node` 并驱动 CLI | **MATCH** |
| 报表系统 | `clawrelay-report` 全栈 + 5173 入口 | `backend/` + `frontend/` 完整，`5173` 为唯一入口 | **MATCH** |
| 禁止路径 | `clawrelay-api` 不再使用 | 零引用，仅作废弃声明 | **MATCH** |

### 总结

**所有验证项均 MATCH。** 实际代码与 `STANDARD.md` 描述的架构完全一致：
- `clawrelay-feishu-server` 正确调用 `claude-node`
- `clawrelay-report` 有完整的前后端实现
- `5173` 是唯一的，管理后台入口
- `clawrelay-api` 已被完全移除，无任何代码引用
