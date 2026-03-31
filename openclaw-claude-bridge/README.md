# clawrelay-bridge

OpenClaw + claude-node Bridge Server - HTTP API wrapper that integrates Claude CLI with OpenClaw.

## Architecture

```
OpenClaw (通讯层)
    │
    │ Provider: claude-node (OpenAI-compatible API)
    ▼
clawrelay-bridge (协议转换层)
    │
    │ Session Mapping
    ▼
claude-node (AI处理层 - Claude CLI subprocess)
```

## Quick Start

### 1. Install Dependencies

```bash
cd clawrelay-bridge
pip install -e .
```

### 2. Configure Environment

```bash
export CLAUDE_MODEL="claude-sonnet-4-6"
export CLAUDE_WORKING_DIR="/path/to/workspace"
export BRIDGE_PORT=18793  # Note: 18792 is used by OpenClaw browser relay
```

### 3. Start Bridge Server

```bash
python -m clawrelay_bridge
# or
clawrelay-bridge
```

### 4. Configure OpenClaw

Add to your `openclaw.json`:

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "claude-node": {
        "baseUrl": "http://127.0.0.1:18792",
        "apiKey": "not-needed",
        "api": "openai-completions",
        "models": [
          {
            "id": "claude-sonnet-4-6",
            "name": "Claude Sonnet 4",
            "input": ["text"],
            "contextWindow": 200000,
            "maxTokens": 8192
          }
        ]
      }
    }
  }
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | OpenAI-compatible chat completions (blocking v1) |
| `/v1/models` | GET | List available models |
| `/health` | GET | Health check and fallback status |

### Health Check

```bash
curl http://127.0.0.1:18792/health
```

Response:
```json
{
  "status": "healthy",
  "claude_node": "connected",
  "fallback_state": "normal",
  "timestamp": "2026-03-29T12:00:00",
  "session_count": 5
}
```

## Fallback Mechanism

When claude-node goes down:
1. Health monitor detects failure (3 consecutive failures)
2. Fallback manager transitions to FALLBACK state
3. OpenClaw activates and runs repair skill
4. When claude-node recovers, system returns to NORMAL state

## Skills

### claude-node-health-check
Periodically check claude-node health status.

### claude-node-repair
Repair and restart claude-node service when issues occur.

## Project Structure

```
clawrelay-bridge/
├── pyproject.toml
├── openclaw.json           # OpenClaw Provider configuration
├── skills/
│   ├── claude-node-health-check/
│   └── claude-node-repair/
└── src/clawrelay_bridge/
    ├── __init__.py
    ├── __main__.py
    ├── config.py
    ├── server.py           # FastAPI server
    ├── session_mapper.py   # Session mapping
    ├── health_monitor.py   # Health checking
    └── fallback_manager.py # Fallback state machine
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BRIDGE_HOST` | `127.0.0.1` | Server bind address |
| `BRIDGE_PORT` | `18792` | Server port |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model to use |
| `CLAUDE_WORKING_DIR` | `` | Working directory for Claude CLI |
| `HEALTH_CHECK_INTERVAL` | `30` | Health check interval (seconds) |
| `FALLBACK_FAILURE_THRESHOLD` | `3` | Failures before fallback |
| `FALLBACK_SUCCESS_THRESHOLD` | `3` | Successes before recovery |
| `BRIDGE_DB_PATH` | `~/.openclaw-claude-bridge/bridge.db` | SQLite database path |
