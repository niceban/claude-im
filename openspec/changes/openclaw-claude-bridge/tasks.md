# openclaw-claude-bridge 实现任务

## 1. 项目初始化

- [x] 1.1 创建项目目录结构
- [x] 1.2 初始化 Python 包（pyproject.toml 或 setup.py）
- [x] 1.3 添加依赖：starlette、uvicorn、claude-node（固定版本号）
- [x] 1.4 配置 pytest 测试框架
- [x] 1.5 记录 claude-node 版本要求（Alpha 状态需固定版本）

## 2. TDD 模式 - openai-compatible-api 模块（必须先通过测试）

### 2.1 测试先行
- [x] 2.1.1 编写 `POST /v1/chat/completions` 单元测试（认证、超时、错误格式）
- [x] 2.1.2 编写 `GET /health` 单元测试（版本动态化）
- [x] 2.1.3 编写 `GET /v1/models` 单元测试
- [x] 2.1.4 编写 usage 字段响应测试

### 2.2 实现
- [x] 2.2.1 实现 `POST /v1/chat/completions` endpoint（含 X-API-Key 认证）
- [x] 2.2.2 实现 `GET /health` endpoint（版本动态读取）
- [x] 2.2.3 实现 `GET /v1/models` endpoint
- [x] 2.2.4 实现统一错误格式（401/429/500）和 usage 字段

### 2.3 验证
- [x] 2.3.1 运行测试，确保全部通过
- [x] 2.3.2 验证 claude-node 版本固定（检查 pyproject.toml 或 lock 文件）

## 3. TDD 模式 - claude-node-adapter 模块

**blockedBy**: task 2.3.1（依赖 openai-compatible-api 测试通过）

### 3.1 测试先行
- [x] 3.1.1 编写 HTTP 到 ClaudeController 格式转换测试
- [x] 3.1.2 编写 Controller 生命周期管理测试（含 SIGTERM/SIGCHLD 处理）
- [x] 3.1.3 编写响应格式转换测试
- [x] 3.1.4 编写错误处理测试（统一错误码）

### 3.2 实现
- [x] 3.2.1 实现请求格式转换
- [x] 3.2.2 实现 Controller 生命周期管理（含 zombie 进程处理）
- [x] 3.2.3 实现响应格式转换
- [x] 3.2.4 实现错误处理（与 API spec 统一错误码）

### 3.3 验证
- [x] 3.3.1 运行测试，确保全部通过
- [x] 3.3.2 跨模块验证：使用 mock ClaudeController 测试 adapter 输出格式

## 4. TDD 模式 - session-mapping 模块

**blockedBy**: task 3.3.1（依赖 claude-node-adapter 测试通过）

### 4.1 测试先行
- [x] 4.1.1 编写 conversation_id 到 session_id 映射测试
- [x] 4.1.2 编写 LRU 驱逐测试
- [x] 4.1.3 编写空闲超时清理测试
- [x] 4.1.4 编写 SessionBackend 抽象接口测试

### 4.2 实现
- [x] 4.2.1 实现 session 映射管理
- [x] 4.2.2 实现 LRU 驱逐逻辑
- [x] 4.2.3 实现空闲超时清理
- [x] 4.2.4 实现 SessionBackend 抽象接口（供 claude-node-adapter 使用）

### 4.3 验证
- [x] 4.3.1 运行测试，确保全部通过
- [x] 4.3.2 跨模块验证：验证与 claude-node-adapter 的集成（mock SessionBackend）

## 5. 配置生成 - models-provider-config

**blockedBy**: task 4.3.1（依赖 session-mapping 测试通过）

### 5.1 实现
- [x] 5.1.1 生成 openclaw.json 配置片段（models.providers 格式）

### 5.2 验证
- [x] 5.2.1 验证 JSON 配置格式正确
- [x] 5.2.2 验证版本固定（claude-node 版本号写入配置）

## 6. 集成测试

**blockedBy**: task 5.2.1（依赖配置生成完成）

### 6.1 测试先行
- [x] 6.1.1 编写 bridge 到 claude-node 集成测试（真实 HTTP 调用）
- [x] 6.1.2 编写 E2E 测试骨架

### 6.2 实现
- [x] 6.2.1 实现完整的 bridge 服务
- [x] 6.2.2 实现服务启动入口

### 6.3 验证
- [x] 6.3.1 运行集成测试（使用真实 claude-node）
- [x] 6.3.2 运行 E2E 测试
- [x] 6.3.3 跨模块端到端验证：完整请求链路测试

## 7. OpenClaw 配置更新

**blockedBy**: task 6.3.2（依赖 E2E 测试通过）

- [x] 7.1 更新 `~/.openclaw/openclaw.json` 的 models.providers（含固定 claude-node 版本）
- [x] 7.2 验证 Gateway 路由到 bridge
- [x] 7.3 测试飞书端到端

## 8. 文档和发布

- [x] 8.1 编写 README.md
- [x] 8.2 更新 CLAUDE.md 项目认知
- [x] 8.3 标记 daemon-pool 归档
