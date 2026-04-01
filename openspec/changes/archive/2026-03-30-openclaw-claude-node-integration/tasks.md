## 1. Bridge Server 基础设施

- [x] 1.1 Create `clawrelay-bridge/` directory structure
- [x] 1.2 Set up Python package with `__init__.py`, `__main__.py`
- [x] 1.3 Add dependencies: `fastapi`, `uvicorn`, `pydantic` (reuse existing if any)
- [x] 1.4 Create config module for port, host, paths

## 2. Session Mapping 实现

- [x] 2.1 Create SQLite schema for `session_mapping` table
- [x] 2.2 Implement `SessionMapper` class with CRUD operations
- [x] 2.3 Add methods: `create_mapping`, `get_by_openclaw_session`, `get_by_claude_session`, `update_last_active`, `archive_session`
- [x] 2.4 Initialize database on startup

## 3. claude-node Bridge 实现

- [x] 3.1 Create `BridgeServer` class wrapping existing `ClaudeNodeAdapter`
- [x] 3.2 Implement `POST /v1/chat/completions` (blocking, v1)
- [x] 3.3 Implement `GET /v1/models` returning model list
- [x] 3.4 Implement `GET /health` returning health status
- [x] 3.5 Wire up session routing through SessionMapper

## 4. Health Monitor 实现

- [x] 4.1 Create `HealthMonitor` class with periodic checking
- [x] 4.2 Implement claude-node liveness check (ping/health call)
- [x] 4.3 Add configurable check interval (default 30s)
- [x] 4.4 Connect health status to `/health` endpoint

## 5. Fallback Manager 实现

- [x] 5.1 Create `FallbackManager` class with state machine
- [x] 5.2 Implement NORMAL → FALLBACK transition on 3 consecutive failures
- [x] 5.3 Implement FALLBACK → NORMAL transition on 3 consecutive successes
- [x] 5.4 Add callback hooks for state change notifications

## 6. OpenClaw Provider 配置

- [x] 6.1 Create `openclaw.json` Provider configuration for claude-node Bridge
- [x] 6.2 Configure `models.providers.claude-node` with baseUrl, api type, model list
- [ ] 6.3 Test Provider loads and connects to Bridge Server

## 7. OpenClaw Skill 实现 (Fallback)

- [x] 7.1 Create `claude-node-health-check` Skill
- [x] 7.2 Skill calls Bridge `/health` endpoint
- [x] 7.3 Create `claude-node-repair` Skill for fallback mode
- [x] 7.4 Skill attempts to restart claude-node service

## 8. 集成测试

- [x] 8.0 单元测试 (84 tests passed)
- [x] 8.1 Start Bridge Server, verify `/health` returns healthy
- [ ] 8.2 Start OpenClaw with claude-node Provider configured
- [x] 8.3 Send test message, verify routes through Bridge to claude-node
- [x] 8.4 Verify session mapping is created in database
- [ ] 8.5 Test fallback: stop claude-node, verify OpenClaw activates

## 9. 代码归档

- [x] 9.1 Archive `clawrelay-feishu-server/` to `archive/clawrelay-feishu-server/`
- [x] 9.2 Archive `clawrelay-report/` to `archive/clawrelay-report/`
- [x] 9.3 Update project README with new architecture

## 10. 文档更新

- [x] 10.1 Update architecture docs with new `clawrelay-bridge/` structure
- [x] 10.2 Document Provider configuration process
- [x] 10.3 Add run instructions for Bridge Server

**注意**: STANDARD.md 需要同步更新以反映新架构
