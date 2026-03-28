# ROOT_CAUSE.md — 飞书 Bot 问题排查

## 问题清单
1. 思考中的时候不用发消息
2. ~~打字中未取消~~ → 已移除 typing indicator
3. 现在消息回复特别慢
4. 未生成文本回复（send 超时返回 None）
5. Markdown 不完整（lark_md 不支持标题/代码块）
6. ~~ATX 标题 `## 标题` 原样显示~~ → `_preprocess_markdown()` 预处理为 `**标题**`（粗体）

---

## Issue 1: 思考中发送不必要消息

**根因**：`_make_stream_card_callback` 在首次发送卡片时用 `"**正在思考...**"` 作为初始内容，第一张卡在 AI 第一个字符到达前就被发送了。

**修复**：将初始卡片 elements 改为空内容 `""`，只等待真实内容到达才发送。

---

## Issue 2: Typing Indicator（已移除）

**历史方案**：用飞书 emoji reaction 模拟打字动画，每 4 秒 delete + create 刷新防止动画消失。

**问题**：`delete_reaction` + `create_reaction` 之间有间隙，导致 emoji 闪烁（Flicker）。

**最终方案**：完全移除 typing indicator，保留简洁的流式卡片体验。

**代码变更**：
- 移除所有 `add_reaction` / `delete_reaction` 调用链
- 移除 `reaction_id`、`reaction_ids`、`typing_task` 状态
- 移除 `_refresh_typing()` 函数

---

## Issue 3: 回复特别慢

**根因**：ClaudeController 子进程每次启动需要等待初始化（`wait_init_timeout=30`），如果 subprocess 未预热，首次消息需要等 30 秒。

**修复**：在 server 启动时调用 `adapter.prewarm()`，在服务就绪前完成 controller 初始化，消除首次消息的冷启动延迟。

```python
# message_dispatcher.py __init__ 中
self.orchestrator.adapter.prewarm()
```

---

## Issue 4: 未生成文本回复

**根因**：`send(timeout=300)` 的 300 秒超时被触发时，返回值 `data=None`。adapter 的 fallback 逻辑：

```python
elif tag == "done":
    result = data   # data=None（超时返回）
    if not text_accumulated and result:  # result=None 时短路
        # 未 yield 任何 TextDelta
```

导致 orchestrator 侧 `accumulated_text` 仍为 `""`，触发"未生成文本回复"错误提示。

**修复**：
1. 超时改为 1 小时（`timeout=3600`）
2. session 锁等待同步改为 1 小时（`timeout=3600.0`）
3. adapter 层显式处理 `result is None` 的情况，yield 超时提示

```python
elif tag == "done":
    result = data
    if result is None:
        if not text_accumulated:
            yield TextDelta(text="[系统] AI 处理超时（1小时），请稍后重试或尝试更具体的问题。")
    elif not text_accumulated:
        fallback = ...
```

---

## Issue 5: Markdown 表格渲染（静态 vs 流式）

### 静态渲染（finish 后）：✅ 已解决

**历史根因**：
- `lark_md` 在 `div` 里只支持 bold/italic/strikethrough，**不支持标题/代码块/列表**
- `update_multi: true` 的卡不支持 patch 时切换元素类型

**修复（V2）— 当前版本**：
- 飞书有原生 `table` 组件（V7.4+），支持真表格（网格+表头+分页）
- `_parse_markdown_tables()` 从 markdown 文本中解析 `|col|col|` 表格
- 解析为飞书原生 `table` 组件，单元格使用 `markdown` data_type（V7.14+）
- 非表格内容继续用 `markdown` 组件

**table 组件 schema**（官方文档确认 + Shiien/metabot 实测验证）：
```json
{
  "tag": "table",
  "page_size": 5,
  "row_height": "low",
  "freeze_first_column": false,
  "columns": [
    {"name": "列名", "display_name": "列名", "data_type": "markdown"}
  ],
  "rows": [{"列名": "单元格内容"}]
}
```

**支持的 data_type**：

| data_type | 说明 | 版本 |
|-----------|------|------|
| `text` | 纯文本 | 7.4+ |
| `markdown` | 完整 markdown | **7.14+**（用户版本 7.64.6 满足） |
| `number` | 数字+格式 | 7.4+ |
| `date` | 时间戳 | 7.6+ |
| `lark_md` | 部分 markdown | 7.10+ |

**注意事项**：
- 表格必须包含表头+至少一行数据
- 每个 card 最多 5 个 table 组件
- 流式场景下（边输出边显示），完整表格到达后才渲染为 table 组件；未完整到达时降级为 markdown 文本

### 流式渲染（边输出边显示）：❌ 社区无解

**当前实现已切换为方案1（静默等待）**

用户选择方案1：finish 后一次性发送完整卡片，流式过程中完全不推送。

```python
async def on_stream_delta(accumulated_text: str, finish: bool):
    if not finish:
        return  # 静默等待 — 流式过程中完全不推送
    # finish 时一次性发送完整内容（完整表格渲染为 native table）
    ...
```

**根因**：
- `_parse_markdown_tables()` 依赖完整表格结构（表头行 + 分隔行 `|---|` + 数据行）
- 流式过程中，AI 输出 `|city|score|` 后，分隔行和数据行尚未到达
- 此时 `len(data_lines) < 2`，表格不触发，原始 `|col|col|` 被当作 markdown 文本渲染

**调研结论**：
- **Shiien/metabot（2026-03-17 合并）** 实现完全相同的方案，也是 finish 后才渲染表格
- **所有已知飞书 bot 实现均如此** — 社区没有流式表格渲染的先例
- 飞书 `table` 组件不支持增量行添加（patch_card 需全量替换整表）
- 理论上可以先发不完整表格再 patch，但飞书 table 组件在行数变化时的渲染行为未文档化

**当前策略**：
- finish 前：表格内容以 markdown 文本形式显示（`|col|col|` 原始语法，用户可见但不美观）
- finish 后：`_parse_markdown_tables()` 全量解析，patch_card 一次性替换为原生 table 组件

**可能的优化方向（未验证）**：
- 等待分隔行 `|---|` 到达后，立即发送含表头的 table 组件（数据行为空）
- 后续每个数据行到达时，patch_card 全量替换整个 table（性能开销较大）
- 需自行验证 table 组件在行数变化时的 patch 行为

---

## Issue 6: ATX 标题 `## 标题` 原样显示

**根因**：飞书 markdown 组件官方文档明确不支持 ATX 标题语法（`# ## ###`），`## 文本` 会原样显示。

**调研结论**（官方文档确认）：
- ✅ 支持：`**粗体**`、`*斜体*`、`~~删除线~~`、链接、列表、代码块
- ❌ 不支持：ATX 标题 `# ## ###`

**修复**：`on_stream_delta` 在 `finish` 时调用 `_preprocess_markdown()`：

```python
# 预处理：将 ## 标题 → **标题**（粗体，飞书支持）
elements = _parse_markdown_tables(_preprocess_markdown(accumulated_text))
```

```python
def _preprocess_markdown(content: str) -> str:
    # ATX 标题：行首 # + 空格 + 标题文本
    content = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', content, flags=re.MULTILINE)
    return content
```

**注意**：代码块内的 `##` 也会被转换（极少数场景，可接受）。`header.title` 的 `plain_text` 仍然不支持 markdown（平台限制，标题放 `elements[0]` 的 markdown 组件里可渲染）。

---

## 调研方向（已解决）

1. ✅ Feishu `im.messageReaction` API：reaction 不会自动清除，必须显式删除（但 typing indicator 已移除）
2. ✅ Feishu 是否有原生 typing API：没有，emoji reaction 方案因闪烁问题已废弃
3. ✅ claude-node 冷启动优化：添加 `prewarm()` 机制
4. ✅ `send()` 超时返回 None：显式处理并给出友好提示
5. ✅ markdown 组件 vs lark_md：全程 markdown 组件绕过元素切换限制
6. ✅ markdown 表格 → native table：`_parse_markdown_tables()` 实现，finish 后全量渲染
7. ✅ 流式表格渲染：**社区无解**，所有实现均 finish 后一次性渲染（包括 Shiien/metabot）
