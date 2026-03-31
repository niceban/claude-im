# Claude-IM 唯一标准

> 本文件是 `/Users/c/claude-im` 的唯一标准。
> 任何其他文件、历史讨论、隐藏目录、AI 过程稿，只要与本文件冲突，都以本文件为准。

## 1. 最终拍板的四个结论

### 1.1 IM 执行链路

IM 侧采用 **OpenClaw + claude-node** 的分层方案。

标准链路：

```text
Feishu / WeCom / ...
  -> OpenClaw (通讯层，24+ 消息通道)
  -> openclaw-claude-bridge (Provider 协议转换)
  -> claude-node (AI 处理层，Claude CLI subprocess)
  -> Claude Code CLI
```

OpenClaw 作为通讯层，通过 Provider 插件机制调用 claude-node。

**Fallback 机制**：claude-node 宕机时，OpenClaw 上线执行维修任务，修好后立即下线。

**已废弃**：
- `clawrelay-feishu-server` → 已归档
- `clawrelay-report` → 已归档
- `clawrelay-api` → 不再属于标准架构

### 1.2 报表 / 管理后台

报表系统采用 **`clawrelay-report` 的全栈方案**，必须包含：

- 后端
- 前端
- 真实数据接入

标准链路：

```text
clawrelay-feishu-server
  -> clawrelay-report backend
  -> clawrelay-report frontend
```

它不是 Grafana-only 的替代品，也不是纯展示壳子。

**唯一管理后台入口**：

```text
http://localhost:5173
```

说明：

- `5173` 是唯一对人使用的管理后台入口
- `8000` 只是 `clawrelay-report` 的内部后端 API 服务
- 不允许再把其他页面、其他工具、其他面板写成并列后台

### 1.3 SSE 状态

SSE **目前不算已确认能力**。

标准表述只能是：

- 还没有测透
- 不能写成“已经实现”
- 在有明确验证结果之前，一律按“未确认 / 很可能还没有”处理

### 1.4 文档治理

本仓库只允许一套标准叙事，不允许再保留平行版本。

## 2. 本仓库的定位

`/Users/c/claude-im` 现在的定位是：

- 项目标准仓
- 统一口径仓
- 辅助脚本仓

它不是以下系统的主源码仓：

- `clawrelay-feishu-server`
- `claude-node`
- `clawrelay-report`

这些系统都在本仓库之外单独存在。

## 3. 标准工作区布局

```text
/Users/c/claude-im                  # 标准文档 + 辅助脚本
/Users/c/openclaw-claude-bridge    # OpenClaw Provider bridge，直连 claude-node
/Users/c/archive/                   # 已归档的历史代码
    clawrelay-feishu-server/        #   - 旧版飞书 IM 适配层
    clawrelay-report/               #   - 旧版报表系统
```

## 4. 标准架构说明

### 4.1 通讯层 (OpenClaw)

OpenClaw 作为通讯层，必须满足：

- 24+ 消息通道支持（Feishu、Discord、Slack 等）
- Gateway WebSocket 协议（ws://127.0.0.1:18789）
- Provider 插件机制调用外部 AI 引擎

### 4.2 协议转换层 (openclaw-claude-bridge)

openclaw-claude-bridge 是 OpenClaw Provider 封装，必须满足：

- OpenAI-compatible HTTP API（POST /v1/chat/completions）
- Session 映射（OpenClaw session ↔ claude-node session）
- 健康检查和 Fallback 触发

### 4.3 AI 处理层 (claude-node)

`claude-node` 是 AI 处理层，标准期待：

- 直接 spawn Claude Code CLI
- 支持 `resume`
- 支持 CLI 原生工具能力
- Session 生命周期管理

### 4.3 报表层

`clawrelay-report` 是唯一标准的报表/后台产品。

它应该承担：

- 认证后的后台访问
- 后端 API 聚合与加工
- 前端管理页面和报表页面
- 对真实业务数据的接入与展示

以下内容都不能替代它：

- Grafana 作为主产品界面
- 只有图表没有业务后台
- 假数据面板

### 4.4 数据原则

所有面板必须基于真实业务数据。

明确禁止：

- 空面板
- 假数据占位后却写成“已完成”
- 没验证 SSE 却宣称支持实时流式

## 5. 当前唯一可信的状态表

| 主题 | 标准结论 |
|------|------|
| IM 执行路径 | OpenClaw + openclaw-claude-bridge + claude-node |
| 归档组件 | `clawrelay-feishu-server`、`clawrelay-report` 已归档 |
| Provider 机制 | openclaw-claude-bridge 作为 OpenClaw Provider |
| Fallback | claude-node 宕机时 OpenClaw 上线维修 |
| SSE | 未确认，不得默认视为已实现 |
| 隐藏 AI 讨论材料 | 非标准内容，不应保留为平行真相 |

## 6. 明确废弃的路线

以下路线全部视为废弃或非标准：

- `clawrelay-api` 与 `claude-node` 双路线并存
- 用 `clawrelay-api` 作为当前主运行链路
- 用 Grafana 充当标准报表产品
- 把 SSE 写成既成事实
- 保留大量 AI 过程稿作为平行架构文档

## 7. 文档层级

本仓库文档层级固定为：

1. `STANDARD.md`：唯一标准
2. `README.md`：入口说明，只负责指向 `STANDARD.md`
3. `AGENTS.md`：给 agent 的约束，必须和 `STANDARD.md` 一致

除此之外，不再保留第二套架构文档、第二套需求文档、第二套调研结论。

## 8. 变更规则

以后只允许按下面的顺序改：

1. 先改 `STANDARD.md`
2. 再改相关脚本或说明
3. 最后再改外部代码仓

如果代码与本文件冲突，只能二选一：

- 把代码改回标准
- 在同一个变更里修订本文件

## 9. 脚本约束

本仓库 `scripts/` 下的脚本必须遵守：

- 不能再引用 `clawrelay-api`
- 不能把 Grafana 写成主后台
- 不能暗示 SSE 已经可用

## 10. 一句话总结

```text
项目标准已经收敛为：IM 侧直连 claude-node，唯一管理后台入口是 http://localhost:5173，对应 clawrelay-report 全栈方案，SSE 暂未确认，本文件是唯一标准。
```
