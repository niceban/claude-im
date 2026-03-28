# System Availability Challenges - Challenge Report

**Role**: challenger
**Date**: 2026-03-28
**Session**: BRS-syscheck-20260328
**Checked Components**: clawrelay-feishu-server, clawrelay-report, claude-node

---

## Critical Issues

### 1. DATA FLOW BREAKPOINT - Port Mismatch (CRITICAL)

**Location**: `clawrelay-report/backend/app/integrations/clawrelay.py:18` vs `clawrelay-feishu-server/admin_server.py:89`

**Problem**: The report backend expects feishu-server to expose Admin API on port **8088**, but the actual admin server runs on port **8080**.

```python
# clawrelay-report/backend/app/integrations/clawrelay.py
CLAWRELAY_BASE_URL = "http://localhost:8088"  # <-- WRONG

# clawrelay-feishu-server/admin_server.py
parser.add_argument("--port", type=int, default=8080, help="监听端口")  # <-- 8080
```

**Impact**: All API calls from clawrelay-report to clawrelay-feishu-server fail with connection refused:
- `GET http://localhost:8088/api/v1/metrics` -> Connection refused
- `GET http://localhost:8088/api/v1/sessions` -> Connection refused

**Evidence**: Log shows feishu-server admin listening on 8080, but report backend trying 8088.

---

### 2. Feishu WebSocket Unstable Connection (CRITICAL)

**Location**: `clawrelay-feishu-server/src/transport/feishu_ws_client.py`

**Problem**: The feishu-server.log shows repeated WebSocket disconnections:

```
[Lark] [2026-03-28 12:24:03,423] [ERROR] receive message loop exit, err: no close frame received or sent
[Lark] [2026-03-28 12:24:28,063] [INFO] trying to reconnect for the 1st time
[Lark] [2026-03-28 12:24:33,096] [ERROR] connect failed, err: ('Connection aborted.', ConnectionResetError(54, 'Connection reset by peer'))
```

**Impact**:
- Messages are lost during disconnection window
- Users experience silent failures (no error shown, message simply not processed)
- Multiple rapid reconnections can cause message duplication

---

### 3. Hardcoded File Path - Not Portable (CRITICAL)

**Location**: `clawrelay-report/backend/app/integrations/clawrelay.py:19`

```python
CHAT_LOG_PATH = Path("/Users/c/clawrelay-feishu-server/logs/chat.jsonl")
```

**Problem**: Path is hardcoded to a specific user's home directory. When deployed in Docker containers:
- The path `/Users/c/clawrelay-feishu-server` does not exist in the container
- The clawrelay-report backend cannot read chat logs when running in its own container

**Impact**: Chat history and statistics are unavailable in production Docker deployment.

---

## Important Issues

### 4. No Health Monitoring for ClaudeNode Subprocess

**Location**: `clawrelay-feishu-server/src/adapters/claude_node_adapter.py:514-524`

**Problem**: The `check_health()` method exists but is never called. No background loop monitors Claude CLI subprocess health.

```python
async def check_health(self) -> bool:
    """健康检查（检查所有 session 的 controller）"""
    # This method is never called by any scheduler
```

**Impact**: If Claude CLI subprocess crashes, there is no automatic detection or recovery. The system continues to fail requests silently.

---

### 5. Session Manager Race Condition on Startup

**Location**: `clawrelay-feishu-server/src/core/session_manager.py:77-110`

**Problem**: `_ensure_cache_loaded()` is called from multiple threads without proper double-check locking:

```python
def _ensure_cache_loaded(self):
    if self._cache_loaded:  # <-- First check (no lock)
        return
    with self._lock:  # <-- Lock only after first check
        if self._cache_loaded:  # <-- Second check
            return
        # ... load from SQLite
```

The `__init__` method calls this directly in the constructor, but also spawns a daemon thread for SQLite init.

**Impact**: Potential for multiple threads to simultaneously attempt cache loading.

---

### 6. Session Timeout Logic Bug

**Location**: `clawrelay-feishu-server/src/core/session_manager.py:119-135`

**Problem**: `get_relay_session_id()` uses `time.monotonic()` but `save_relay_session_id()` stores `time.time()` values. These are different time bases:

```python
# save_relay_session_id uses time.time()
now = time.time()

# get_relay_session_id uses time.monotonic()
elapsed = time.monotonic() - entry["last_active"]
```

**Impact**: Session timeout calculations may be incorrect (off by hours or days) because `time.monotonic()` and `time.time()` have different epoch references.

---

### 7. Hot Reload PID File Never Written

**Location**: `clawrelay-feishu-server/main.py` and `clawrelay-feishu-server/src/admin/routes.py:129`

**Problem**: The hot reload mechanism reads from a PID file that is never created:

```python
# routes.py - tries to read PID
pid_file = Path.home() / "clawrelay-feishu-server" / "bot.pid"
if pid_file.exists():
    pid = int(pid_file.read_text().strip())
    os.kill(pid, signal.SIGUSR1)
```

But `main.py` never writes this file on startup.

**Impact**: The hot reload feature (`SIGUSR1`) is non-functional. Config changes via API fail with "进程不存在或无权限".

---

### 8. Missing Message Redelivery Handling

**Location**: `clawrelay-feishu-server/src/transport/message_dispatcher.py:336-340`

**Problem**: The message deduplication uses a simple in-memory dictionary with 5-minute expiry:

```python
self._processed_msgids: dict[str, float] = {}

def _cleanup_processed_msgids(self):
    now = time.time()
    expired = [k for k, v in self._processed_msgids.items() if now - v > 300]
    for k in expired:
        del self._processed_msgids[k]
```

**Impact**: After process restart, all message IDs are forgotten. If Feishu retries a message during a brief disconnection, it will be processed twice.

---

## Moderate Issues

### 9. Admin API Has No Authentication

**Location**: `clawrelay-feishu-server/src/admin/routes.py`

**Problem**: All admin endpoints (`/metrics`, `/sessions`, `/config/*`) are open with no authentication:

```python
@router.get("/sessions")
async def list_sessions(bot_key: Optional[str] = None):
    # No auth check - anyone can list all sessions
```

**Impact**: Anyone with network access to port 8080 can:
- View all active sessions and their metadata
- View bot configuration (including system prompts)
- Trigger configuration reloads

---

### 10. CORS Allows All Origins in Production

**Location**: `clawrelay-feishu-server/admin_server.py:45-51`

```python
admin_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # <-- Permissive for all environments
    ...
)
```

**Impact**: In production, the admin API should restrict cross-origin requests to only the legitimate frontend domain.

---

### 11. App Secret Hardcoded in Config Files

**Location**: `clawrelay-feishu-server/config/bots.yaml:4`

```yaml
app_secret: "woV3uOvc7GBI05CNhjoWGfdfuSUsYk4u"
```

**Impact**:
- Secrets are committed to version control (see git status showing modified files)
- The .env file also contains the secret in plain text

---

### 12. WebSocket Reconnection May Cause Duplicate Events

**Location**: `clawrelay-feishu-server/src/transport/feishu_ws_client.py:66`

```python
self._ws_client = WsClient(
    ...
    auto_reconnect=True,  # SDK handles reconnection
)
```

**Problem**: When the SDK reconnects after a network blip, it may replay missed messages. The client-side deduplication is in-memory only and expires after 5 minutes.

**Impact**: During network instability, users may receive duplicate message processing.

---

## Single Points of Failure

| Component | SPOF Description | Severity |
|-----------|------------------|----------|
| Feishu WebSocket | Single connection - no fallback | CRITICAL |
| Claude CLI subprocess | Single point - no HA cluster | CRITICAL |
| Local SQLite sessions | Sessions lost on disk failure | HIGH |
| chat.jsonl file | Single file, no rotation/backup | HIGH |
| Admin API port 8080 | No port sharing/monitoring | MEDIUM |

---

## Data Flow Verification

```
feishu-server (WS) --> message_dispatcher --> claude_node_adapter --> Claude CLI (subprocess)
                                           --> chat_logger --> chat.jsonl
                                           --> feishu_api --> Feishu (response)

clawrelay-report frontend (:5173) --> clawrelay-report backend (:8000)
                                           |
                                           +--> GET http://localhost:8088/api/v1/metrics (FAILS - wrong port)
                                           +--> Read /Users/c/clawrelay-feishu-server/logs/chat.jsonl (FAILS - wrong path in Docker)
```

**Data flow is broken at two points**:
1. Report backend cannot reach feishu admin API (port 8088 vs 8080)
2. Report backend cannot read chat logs (hardcoded path + Docker filesystem)

---

## Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 3 | Port mismatch, WebSocket instability, hardcoded path |
| IMPORTANT | 4 | No health monitoring, race conditions, PID file bug |
| MODERATE | 5 | Auth gaps, CORS, secrets exposure |

**Verdict**: System is NOT fully operational. The clawrelay-report dashboard cannot retrieve data from clawrelay-feishu-server due to port mismatch and path issues. The Feishu WebSocket connection shows instability with repeated disconnections.

---

## Recommendations

1. **Fix port mismatch**: Change `CLAWRELAY_BASE_URL` to `http://localhost:8080` or run admin on 8088
2. **Externalize configuration**: Use environment variables for paths and ports
3. **Add health check loop**: Schedule periodic `check_health()` calls with alerting
4. **Write PID file**: On main.py startup, write PID to `~/.clawrelay-feishu-server/bot.pid`
5. **Fix time base mismatch**: Use consistent `time.time()` or `time.monotonic()` for session timeouts
6. **Add message redelivery protection**: Use a persistent store (Redis) for deduplication