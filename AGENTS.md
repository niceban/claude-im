# Claude-IM Agent Notes

`/Users/c/claude-im/STANDARD.md` 是本项目唯一标准。

## 固定结论

1. IM 链路是 **直连 `claude-node`**
2. `clawrelay-api` **不再属于标准架构**
3. 报表 / 后台是 **`clawrelay-report` 全栈**
4. 唯一管理后台入口是 **`http://localhost:5173`**
5. SSE **未确认**，默认不得写成“已实现”

## Agent 必须遵守

- 任何时候优先服从 `STANDARD.md`
- 不得把 `clawrelay-api` 重新写回文档、脚本、架构总结
- 不得把 Grafana 写成标准报表产品
- 不得把 `8000` 或其他地址写成并列后台入口；`8000` 只是 `5173` 背后的 API
- 不得在没有明确验证时宣称 SSE 可用
- 只要历史文件、隐藏目录、旧讨论与标准冲突，就应删除或覆盖，不能并存

## 标准工作区

```text
/Users/c/claude-im
/Users/c/clawrelay-feishu-server
/Users/c/clawrelay-wecom-server
/Users/c/claude-node
/Users/c/clawrelay-report
```

## 文档层级

唯一允许的文档层级：

1. `STANDARD.md`
2. `README.md`
3. `AGENTS.md`

其他文档如果不能和这三者严格一致，就不应该保留。
