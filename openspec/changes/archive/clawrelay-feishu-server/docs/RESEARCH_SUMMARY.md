# RESEARCH_SUMMARY.md — 飞书 Bot 关键决策记录

---

### 6. 流式表格渲染 — 社区最优解调研

**问题**：流式过程中，AI 输出 `|表头|` 时，由于缺少分隔行和完整数据，不完整的表格被当作普通 markdown 文本渲染。

**调研结论：社区无解**

| 方案 | 可行性 | 说明 |
|------|--------|------|
| 渐进式构建（先发表头后填数据） | ❌ 未确认 | 飞书 table 组件不支持增量行添加，patch 需全量替换 |
| 流式期间保持文本，等 finish 后一次性渲染 | ✅ 当前方案 | Shiien/metabot 及其他所有实现均如此 |
| 分块输出（不等完整表格） | ⚠️ 体验差 | 用户会看到不完整的 markdown 表格语法 |
| **真正的流式表格** | ❌ 社区无先例 | GitHub 所有飞书 bot 实现均无此功能 |

**关键发现：Shiien/metabot（2026-03-17 合并）**

GitHub 上有完全相同的 markdown → native table 转换实现：

```javascript
// tableRegex: 捕获 表头行 + 分隔行 + 数据行
const tableRegex = /(?:^|\n)((?:\|[^\n]+\|?\n)(?:\|[\s:|-]+\|?\n)(?:(?:\|[^\n]+\|?\n?)*))/g;

// data_type 使用 'lark_md'（而非 'markdown'）
columns: table.headers.map((h, i) => ({
  name: `col_${i}`,
  display_name: stripMarkdown(h),  // 表头需去除 markdown 格式
  data_type: 'lark_md',
  width: 'auto',
})),

// stripMarkdown 去除 **bold**, *italic*, ~~strike~~, `code`, [text](url)
function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/~~(.+?)~~/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
}
```

**与当前实现的差异：**

| 字段 | Shiien/metabot | 当前实现 |
|------|----------------|---------|
| `data_type` | `'lark_md'` | `"markdown"` |
| `display_name` | `stripMarkdown(h)` 纯文本 | `h` 原始 markdown |
| Cell 内容 | `stripMarkdown(cell)` | 原始 markdown |
| `header_style.background_style` | `'grey'` | `'none'` |
| `header_style.text_color` | 未使用 | `'grey'` |
| `page_size` | `rows.length`（无上限） | `min(len(rows)+1, 10)` |

**关于 data_type 的选择：**
- `lark_md`（V7.10+）：部分 markdown（bold/italic/strikethrough）
- `markdown`（V7.14+）：完整 markdown（标题/代码块/列表/链接）
- 用户版本 7.64.6 两者均支持，`markdown` 功能更全

**流式场景的终极限制：**
所有现有实现（包括 Shiien/metabot）都是在 **finish 后**做全量表格转换。流式过程中，无论多短的发帧间隔，都无法把不完整的 `|col|col|` 变成表格。

---

## 核心结论

### 1. Typing Indicator — 已移除

**决策**：完全移除 typing indicator。

**原因**：
- Feishu 没有原生的 typing indicator API，只能用 emoji reaction 模拟
- emoji 动画约 3 秒后消失，需要每 4 秒 delete + create 刷新
- delete 和 create 之间存在间隙，导致明显闪烁（Flicker）
- 调研 Clawdbot-feishu 发现其用 AI 主动控制 emoji 生命周期（AI 调用 tool_use），但引入架构复杂度

**结论**：简洁的流式卡片体验 > 有瑕疵的 typing 动画

---

### 2. "未生成文本回复" — 超时 + None 处理

**场景**：Claude Code 执行长任务（如深度研究）接近 5 分钟时，`send(timeout=300)` 超时返回 `None`。

**根因链条**：
```
send() 超时 → data=None → tag="done" → result=None → and result 短路 → 未 yield → accumulated_text=""
```

**修复**：
1. `send(timeout=300)` → `send(timeout=3600)`（1小时）
2. session 锁等待同步改为 3600 秒
3. adapter 层显式处理 `result is None`：
   ```python
   if result is None:
       yield TextDelta(text="[系统] AI 处理超时（1小时）...")
   ```

---

### 3. Markdown 渲染 — 全程 markdown 组件

**问题**：`lark_md` 在 `div` 里只支持 bold/italic/strikethrough，不支持标题/代码块/列表。

**旧方案**：流式用 `div+lark_md`，finish 时 patch 为 `markdown` 组件。

**阻碍**：`update_multi: true` 的卡不支持 patch 时切换元素类型（error 230904）。

**新方案**：移除 `update_multi`，**全程使用 `markdown` 组件**。

| 语法 | lark_md（div内） | markdown 组件 |
|------|-----------------|--------------|
| bold `**` | ✅ | ✅ |
| italic `*` | ✅ | ✅ |
| strikethrough `~~` | ✅ | ✅ |
| 代码块 ` ``` ` | ❌ | ✅ |
| 有序/无序列表 | ❌ | ✅ |
| 链接 | ✅ | ✅ |

---

### 4. Markdown 表格 → 原生 table 组件

**问题**：`|col|col|` markdown 表格在飞书里不渲染，显示原始符号。

**调研结果**：
- `markdown` 组件**不支持** GFM 表格语法（官方文档确认）
- 飞书有原生 `table` 组件（V7.4+），但需要手动构造 JSON
- Python SDK（lark-oapi）没有 table 封装类，需直接构造 dict
- 单元格 `data_type=markdown`（V7.14+）支持完整 markdown
- **流式场景：社区无解**，所有实现均须等完整表格才能渲染

**修复**：`_parse_markdown_tables()` 自动解析 markdown 表格为原生 table 组件。

---

## 当前架构（最终版）

```
用户发消息
    ↓
accumulated_text 有内容 → send_card() 发初始卡片（markdown 组件）
    ↓
AI 流式输出 → patch_card() 节流更新（500ms，每处都是 markdown 组件）
    ↓
finish=True → patch_card 最终内容 → 完成
```

**无 typing indicator，无元素类型切换，无 update_multi。**

---

## Feishu API 关键行为（实测确认）

| 行为 | 结论 |
|------|------|
| reaction 不会自动清除 | 必须显式 delete（但 typing indicator 已移除） |
| `update_multi` 阻止元素类型切换 | 移除 update_multi 解决 |
| markdown 组件需 Feishu ≥ 7.6 | 用户版本 7.64.6 满足 |
| `send()` 超时返回 None | 显式处理 None + 延长超时 |
| table 组件不支持增量行添加 | patch 需全量替换，流式渐进构建不可行 |
