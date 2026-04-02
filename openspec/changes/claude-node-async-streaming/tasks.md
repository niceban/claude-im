# claude-node-async-streaming 实现任务

**TDD规范**：每个模块先写测试，测试通过后再实现。下一个模块依赖上一个模块测试通过。

---

## Phase 1: 核心可用（Stub替换）

### 模块1: stub-api（HTTP层Stub替换）

**blockedBy**: 无

#### 1.1 测试先行
- [x] 1.1.1 编写 `chat_completions` 调用adapter的测试（mock adapter.send_message）
- [x] 1.1.2 编写 响应不是占位符的断言测试
- [x] 1.1.3 编写 adapter返回错误时的error format测试
- [x] 1.1.4 编写 session_id提取和传递的测试

#### 1.2 实现
- [x] 1.2.1 替换 `server.py` chat_completions，调用 `adapter.send_message()`
- [x] 1.2.2 实现从request提取conversation_id → session_id映射
- [x] 1.2.3 实现adapter返回结果的OpenAI格式转换
- [x] 1.2.4 实现错误传播（adapter错误 → API错误格式）

#### 1.3 验证
- [x] 1.3.1 运行测试，确保全部通过
- [x] 1.3.2 验证响应内容不是占位符

#### 1.4 重构
- [x] 1.4.1 清理遗留Stub注释代码
- [x] 1.4.2 优化error format统一处理

---

### 模块2: stub-adapter（ClaudeController调用）

**blockedBy**: 1.3.1

#### 2.1 测试先行
- [x] 2.1.1 编写 `controller.send_nowait()` 调用测试
- [x] 2.1.2 编写 `controller.wait_for_result()` 返回结果测试
- [x] 2.1.3 编写 session不存在时创建controller的测试
- [x] 2.1.4 编写 超时返回格式测试

#### 2.2 实现
- [x] 2.2.1 替换 `adapter.py` send()，调用真实 `controller.send()`
- [x] 2.2.2 实现 `send_async()`: send_nowait() + wait_for_result()
- [x] 2.2.3 实现 controller.start() with wait_init_timeout=10s
- [x] 2.2.4 实现 controller.stop() 在session结束时
- [x] 2.2.5 实现 `destroy_session()` 清理subprocess（被lifecycle模块调用）

#### 2.3 验证
- [x] 2.3.1 运行测试，确保全部通过
- [ ] 2.3.2 验证真实调用claude_node（非mock）**← deferred: 需要真实 claude_node CLI 环境**

#### 2.4 重构
- [x] 2.4.1 清理遗留Stub代码
- [x] 2.4.2 优化错误处理逻辑

---

### 模块3: lifecycle（Session与Subprocess联动）

**blockedBy**: 2.3.1

#### 3.1 测试先行
- [x] 3.1.1 编写 `destroy_session` 同时清理backend和subprocess的测试
- [x] 3.1.2 编写 LRU驱逐时subprocess被杀的测试
- [x] 3.1.3 编写 idle timeout清理subprocess的测试
- [x] 3.1.4 编写 SIGTERM处理graceful shutdown的测试
- [x] 3.1.5 编写 zombie subprocess检测和清理的测试

#### 3.2 实现
- [x] 3.2.1 修改 `manager.py` destroy_session()，调用adapter.destroy_session()
- [x] 3.2.2 修改 LRU _evict_lru()，同时杀subprocess
- [x] 3.2.3 修改 cleanup_idle_sessions()，同时杀subprocess
- [x] 3.2.4 实现SIGTERM → shutdown_all() → 杀所有subprocess
- [x] 3.2.5 实现zombie subprocess定期检测和清理

#### 3.3 验证
- [x] 3.3.1 运行测试，确保全部通过
- [x] 3.3.2 验证无zombie subprocess累积

#### 3.4 重构
- [x] 3.4.1 优化cleanup调度逻辑
- [x] 3.4.2 简化backend接口

---

### 模块4: config（OpenClaw配置）

**blockedBy**: 3.3.1

#### 4.1 测试先行
- [x] 4.1.1 编写配置生成正确性的测试
- [x] 4.1.2 编写 API Key校验的测试

#### 4.2 实现
- [x] 4.2.1 生成 models.providers 配置片段
- [x] 4.2.2 固定 claude-node 版本号在配置中
- [x] 4.2.3 验证 API Key环境变量要求

#### 4.3 验证
- [x] 4.3.1 验证 JSON 配置格式正确
- [x] 4.3.2 验证版本号已固定

#### 4.4 重构
- [x] 4.4.1 简化配置生成逻辑

---

## Phase 2: async流式

### 模块5: async-stream（SSE流式）

**blockedBy**: 4.2.1

#### 5.1 测试先行
- [x] 5.1.1 编写 SSE stream响应的测试（OpenAI兼容格式）
- [x] 5.1.2 编写 per-request StreamQueue的测试
- [x] 5.1.3 编写 stream=true/false 开关的测试
- [x] 5.1.4 编写 流式中断处理的测试
- [x] 5.1.5 编写 并发请求隔离的测试

#### 5.2 实现
- [x] 5.2.1 实现 `POST /v1/chat/completions` stream模式
- [x] 5.2.2 实现 per-request StreamQueue（解决race condition）
- [x] 5.2.3 实现 on_message callback → SSE推送
- [x] 5.2.4 实现 stream=false 非流式模式
- [x] 5.2.5 实现流式超时处理

#### 5.3 验证
- [x] 5.3.1 运行测试，确保全部通过
- [ ] 5.3.2 验证真实流式输出（非mock）**← deferred: 需要真实 claude_node CLI**
- [ ] 5.3.3 验证SSE格式符合OpenAI标准**← deferred: 需要真实环境**

#### 5.4 重构
- [x] 5.4.1 提取SSE格式化工具函数
- [x] 5.4.2 优化StreamQueue性能

---

## Phase 3: tmux交互

### 模块6: tmux（交互注入通道）

**blockedBy**: 5.3.1

#### 6.1 测试先行
- [x] 6.1.1 编写 tmux session创建的测试
- [x] 6.1.2 编写 send_keys注入命令的测试
- [x] 6.1.3 编写 capture_pane捕获输出的测试
- [x] 6.1.4 编写 kill_session清理的测试
- [x] 6.1.5 编写 session与ClaudeControllerProcess生命周期绑定的测试
- [x] 6.1.6 编写 tmux crash recovery的测试

#### 6.2 实现
- [x] 6.2.1 实现 TmuxManager class
- [x] 6.2.2 实现 tmux send-keys 交互注入
- [x] 6.2.3 实现 异常pattern检测（Do you want.../Enter choice等）
- [x] 6.2.4 实现 tmux模式开关（默认关闭）
- [x] 6.2.5 实现 tmux session与ClaudeControllerProcess生命周期绑定
- [x] 6.2.6 实现 tmux session数量限制和排队机制
- [x] 6.2.7 实现 tmux crash detection和recovery

#### 6.3 验证
- [x] 6.3.1 运行测试，确保全部通过
- [ ] 6.3.2 手动验证tmux注入功能**← deferred: 需要真实 tmux 环境**
- [ ] 6.3.3 验证session生命周期正确绑定**← deferred: 需要真实环境**

#### 6.4 重构
- [ ] 6.4.1 提取tmux命令行为封装**← deferred: 重构可选**
- [ ] 6.4.2 简化pattern匹配逻辑**← deferred: 重构可选**

---

## Phase 4: 集成测试

### 模块7: integration（端到端）

**blockedBy**: 6.3.1

#### 7.1 测试先行
- [x] 7.1.1 编写真实HTTP请求 → claude_node响应的集成测试
- [x] 7.1.2 编写 conversation_id → session_id映射的集成测试
- [x] 7.1.3 编写 多轮对话的集成测试
- [x] 7.1.4 编写 错误恢复的集成测试

#### 7.2 实现
- [x] 7.2.1 实现 `tests/test_integration.py`
- [x] 7.2.2 实现 `tests/test_e2e.py` 骨架

#### 7.3 验证
- [x] 7.3.1 运行集成测试
- [ ] 7.3.2 运行E2E测试**← deferred: 需要真实 claude_node + bridge 服务**
- [ ] 7.3.3 端到端验证完整请求链路**← deferred: 需要生产环境**

#### 7.4 重构
- [ ] 7.4.1 优化测试fixtures复用**← deferred: 重构可选**
- [ ] 7.4.2 添加性能基准测试**← deferred: 重构可选**

---

## Phase 5: 部署

### 模块8: deployment（Canary部署）

**blockedBy**: 7.3.2（E2E测试需要真实环境完成后才能部署）

#### 8.1 配置
- [ ] 8.1.1 更新 ~/.openclaw/openclaw.json models.providers**← deferred: 需要生产配置**
- [ ] 8.1.2 配置 canary 1% 路由**← deferred: 需要运维操作**
- [ ] 8.1.3 API Key环境变量验证**← deferred: 需要生产环境变量**

#### 8.2 验证
- [ ] 8.2.1 验证 Gateway 路由到 bridge**← deferred: 需要生产部署**
- [ ] 8.2.2 canary 1% 功能验证**← deferred: 需要生产部署**
- [ ] 8.2.3 飞书端到端测试**← deferred: 需要生产环境**

#### 8.3 重构（可选）
- [ ] 8.3.1 优化canary切换脚本**← deferred: 重构可选**
- [ ] 8.3.2 自动化回滚机制**← deferred: 重构可选**

---

## 任务依赖图

```
1.1 → 1.2 → 1.3 ─────────┐
                            ↓
2.1 → 2.2 → 2.3 ─────────┤
                            ↓
3.1 → 3.2 → 3.3 ─────────┤
                            ↓
4.1 → 4.2 ────────────────┤
                            ↓
5.1 → 5.2 → 5.3 ──────────┤
                            ↓
6.1 → 6.2 → 6.3 ──────────┤
                            ↓
7.1 → 7.2 → 7.3 ──────────┤
                            ↓
8.1 → 8.2 ─────────────────┘
```

---

## 任务统计

| Phase | 模块 | 任务数 | blockedBy |
|-------|------|--------|-----------|
| 1 | stub-api | 12 | 无 |
| 1 | stub-adapter | 13 | stub-api |
| 1 | lifecycle | 14 | stub-adapter |
| 1 | config | 8 | lifecycle |
| 2 | async-stream | 15 | config |
| 3 | tmux | 18 | async-stream |
| 4 | integration | 11 | tmux |
| 5 | deployment | 8 | integration |
| **总计** | | **99** | |

> 注：任务数包含TDD各阶段（测试先行/实现/验证/重构）
