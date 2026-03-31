---
name: claude-node-repair
description: Repair and restart claude-node service when it goes down
---

# Claude Node Repair Skill

## Purpose
Repair the claude-node service when it goes down and OpenClaw needs to activate fallback mode.

## Prerequisites

This skill should only be run when:
1. `claude-node-health-check` reports `status: unhealthy`
2. OpenClaw has transitioned to `fallback_state: fallback`

## Repair Steps

### Step 1: Check Service Status

```bash
# Check if claude-node process is running
ps aux | grep claude-node | grep -v grep

# Check if the bridge server is running
ps aux | grep clawrelay-bridge | grep -v grep
```

### Step 2: Attempt Restart

```bash
# Restart claude-node service (if managed by systemd)
systemctl --user restart claude-node

# Or restart bridge server
pkill -f clawrelay-bridge
nohup python -m clawrelay_bridge &
sleep 5
```

### Step 3: Verify Recovery

```bash
# Wait for restart and check health
sleep 10
curl -s http://127.0.0.1:18792/health | jq
```

If health returns `status: healthy`, the repair was successful.

### Step 4: Report Status

If recovery was successful:
- Log: "claude-node service recovered"
- OpenClaw should deactivate fallback mode

If recovery failed:
- Log: "claude-node repair failed, manual intervention required"
- Alert administrators

## OpenClaw Behavior After Repair

Once claude-node is healthy again:
1. OpenClaw receives health check showing `status: healthy`
2. OpenClaw transitions from `fallback_state: fallback` to `fallback_state: normal`
3. OpenClaw goes silent and resumes forwarding messages to claude-node via bridge

## Notes

- This skill should be lightweight and fast-executing
- Multiple consecutive failures should trigger additional diagnostics
- If claude-node keeps failing, check:
  - Claude CLI installation: `which claude`
  - API key configuration
  - Network connectivity
