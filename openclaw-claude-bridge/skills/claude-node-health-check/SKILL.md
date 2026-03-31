---
name: claude-node-health-check
description: Check the health status of claude-node bridge service
---

# Claude Node Health Check Skill

## Purpose
Check if the claude-node bridge service is healthy and responding.

## Usage

### Check Health Status

Call the bridge server health endpoint:

```bash
curl -s http://127.0.0.1:18792/health | jq
```

Expected response:
```json
{
  "status": "healthy",
  "claude_node": "connected",
  "fallback_state": "normal",
  "timestamp": "2026-03-29T12:00:00",
  "session_count": 5
}
```

### Interpretation

| Status | Meaning |
|--------|---------|
| `healthy` | claude-node is connected and processing |
| `unhealthy` | claude-node is disconnected or not responding |
| `fallback_state: normal` | OpenClaw is in normal mode (silent) |
| `fallback_state: fallback` | OpenClaw is active (repairing) |

## Behavior

- **When status is `healthy`**: No action needed. OpenClaw remains in silent mode.
- **When status is `unhealthy`**: OpenClaw should activate fallback mode and run `claude-node-repair` skill.

## Notes

- This skill is typically called periodically by OpenClaw's health check mechanism
- The actual health check interval is configured in the bridge server (default: 30s)
