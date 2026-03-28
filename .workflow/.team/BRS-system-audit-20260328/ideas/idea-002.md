# System Audit Findings: Service Status

## Topic
完整检查项目现状：识别实际问题 vs 声称完成状态的差异

## Mode
Initial Generation

---

## Service Status Summary

| Service | Port | Status | Details |
|---------|------|--------|---------|
| feishu-server | - | **RUNNING (stale processes)** | Multiple old processes from today; active PID 6304 at 1:35PM |
| clawrelay-report frontend | 5173 | **RUNNING** | vite process (PID 29822) listening |
| clawrelay-report backend | 8000 | **NOT RUNNING** | No process listening |

---

## 1. Process Status

### feishu-server
- **Status**: RUNNING (but with stale processes)
- **Active process**: PID 6304 (`python3 main.py`) from 1:35PM
- **Stale processes**: 5 additional python3 main.py processes from 9:15AM - 10:09AM
- **Problem**: Multiple orphaned processes indicate the restart mechanism is not cleaning up old processes properly
- **Log file**: `/Users/c/clawrelay-feishu-server/feishu-server.log`
- **Recent errors in log**:
  - `processor not found, type: im.message.message_read_v1` (repeating)
  - `processor not found, type: im.chat.member.bot.deleted_v1`

### clawrelay-report frontend
- **Status**: RUNNING
- **Process**: vite (PID 29822) on `localhost:5173`
- **Started**: Today at 5:54PM

### clawrelay-report backend
- **Status**: NOT RUNNING
- **Expected**: FastAPI/Uvicorn on port 8000
- **Problem**: Backend service is not started

---

## 2. Port Status

| Port | Service | Status |
|------|---------|--------|
| 5173 | report frontend | **LISTENING** |
| 8000 | report backend API | **NOT IN USE** |

---

## 3. Configuration Files

### .env Files
| Location | Status | Issues |
|----------|--------|--------|
| `/Users/c/claude-im/.env` | **NOT FOUND** | Scripts expect this file but it does not exist |
| `/Users/c/clawrelay-feishu-server/.env` | EXISTS | Contains actual tokens |
| `/Users/c/clawrelay-report/.env` | EXISTS | Frontend references `localhost:3000`, actual is `5173` |

### bots.yaml
- **Location**: `/Users/c/clawrelay-feishu-server/config/bots.yaml`
- **Status**: EXISTS and properly configured
- **Issue**: Contains hardcoded secrets (should be in .env instead)

### Secrets Found in bots.yaml
```
ANTHROPIC_AUTH_TOKEN=sk-cp-ATSzsFW4KgGl7Nlv8bI2ZR4k3CBN_Jpz-...
FEISHU_APP_SECRET=woV3uOvc7GBI05CNhjoWGfdfuSUsYk4u
```

---

## 4. Startup Scripts Analysis

### scripts/start.sh
- **Path**: `/Users/c/claude-im/scripts/start.sh`
- **Status**: EXISTS and correctly references `$HOME/clawrelay-feishu-server`
- **Issue**: Uses `nohup python3 main.py` which can leave orphaned processes

### scripts/status.sh
- **Path**: `/Users/c/claude-im/scripts/status.sh`
- **Status**: EXISTS
- **Issue**: Uses `grep "python3 main.py"` which matches ALL python3 main.py processes, not just the one in feishu-server directory

---

## 5. Key Problems Identified

### Critical Issues
1. **clawrelay-report backend NOT running** - Port 8000 is not in use, breaking the admin UI functionality
2. **Multiple stale feishu-server processes** - 6 python3 main.py processes running, only 1 is current
3. **.env location mismatch** - Project expects `.env` at `/Users/c/claude-im/.env` but configs are in subdirectories

### Configuration Issues
4. **Hardcoded secrets in bots.yaml** - Tokens should be in .env, not in config file
5. **Frontend FRONTEND_HOST mismatch** - `.env` says `localhost:3000` but vite serves on `5173`

### Process Management Issues
6. **No process cleanup on restart** - Old processes not killed before starting new ones
7. **Process matching too broad** - `grep "python3 main.py"` matches unintended processes

---

## 6. Verification Commands Used

```bash
# Check processes
ps aux | grep -E "(feishu|report|claude)" | grep -v grep

# Check ports
lsof -i :5173 -i :8000

# Check configs
ls -la /Users/c/claude-im/.env /Users/c/clawrelay-feishu-server/.env /Users/c/clawrelay-report/.env
ls -la /Users/c/clawrelay-feishu-server/config/bots.yaml

# Check logs
tail -30 /Users/c/clawrelay-feishu-server/feishu-server.log
```

---

## Summary

The system has **partial functionality**:
- feishu-server IS running (with process management issues)
- report frontend IS running on port 5173
- report backend is NOT running (port 8000 unused)

The admin UI at `http://localhost:5173` will NOT work properly because:
1. The backend API (port 8000) is not serving
2. The frontend cannot reach its backend

**Immediate action required**: Start the report backend service.
