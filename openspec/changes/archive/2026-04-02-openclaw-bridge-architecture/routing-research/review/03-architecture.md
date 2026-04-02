# Architecture Design Review

**Reviewer**: architecture-reviewer
**Date**: 2026-04-02
**Scope**: `openspec/changes/archive/2026-04-02-openclaw-claude-node-integration-findings/`
**Dimension**: MNT (Maintainability)

---

## Verdict: SOUND

The proposed architecture is well-reasoned and correctly aligns with OpenClaw's design philosophy. The research correctly identified that `cliBackends` is a "text-only fallback" path while `models.providers` is the intended primary execution path with full capability support.

---

## Architecture Analysis

### Layer-by-Layer Breakdown

**Layer 1 — External Channel (Feishu)**
- Role: Entry point, IM platform adapter
- Assessment: Correctly placed as the outermost boundary

**Layer 2 — OpenClaw Gateway**
- Role: `adapter only — 渠道接入/会话壳/生态壳`
- Assessment: **Correct**. OpenClaw's fundamental role is ecosystem integration, not business logic. The Gateway should be a thin adapter layer that routes requests and handles channel-specific protocols.

**Layer 3 — models.providers (HTTP custom provider)**
- Role: Standard OpenAI-compatible HTTP interface
- Assessment: **Correct primary path**. The research correctly identified that:
  - `models.providers` supports tools, streaming, and OpenClaw tool integration
  - `cliBackends` is explicitly documented as "safety-net rather than a primary path"
  - Using HTTP provider instead of CLI backend unlocks full Claude Code capabilities
- The `api: "openai-completions"` with `supportsTools: true` configuration is appropriate

**Layer 4 — openclaw-claude-bridge**
- Role: Protocol conversion, session mapping, event distribution
- Assessment: **Appropriate thickness**. This is a thin translation layer between OpenClaw's HTTP protocol and claude-node's internal API. The bridge should:
  - Translate OpenAI-compatible requests to claude-node calls
  - Handle session ID mapping (OpenClaw session ↔ claude-node session)
  - Distribute events (streaming, tool calls, etc.)
  - NOT contain business logic

**Layer 5 — claude-node**
- Role: Claude runtime, `on_message` event stream, session management
- Assessment: **Correct core**. claude-node is the runtime that spawns Claude Code CLI and manages its lifecycle. The proposed use of `ClaudeController`, `on_message` callback, and session abstraction aligns with claude-node's documented architecture.

**Layer 6 — Claude Code CLI**
- Role: Actual autonomous agent
- Assessment: Standard dependency, no issues

**Layer 7 — DB / Control Plane**
- Role: `run_id`, `stage`, `artifact`, `outbound events` (source of truth)
- Assessment: **Architecturally sound**. Externalizing state to a DB/Control Plane is the correct decision for:
  - Long-running conversations that may span multiple sessions
  - Tracking stage events for Feishu card updates
  - Maintaining artifact history
  - run_id → feishu_context mapping persistence

**Layer 8 — Feishu Outbound (Notifier)**
- Role: Stage events → Feishu card updates
- Assessment: **Correct separation**. Decoupling the notifier from the main flow allows asynchronous Feishu updates without blocking the main request path.

---

## Layer Responsibilities

| Layer | Responsibility | Correctly Assigned? |
|-------|---------------|---------------------|
| OpenClaw Gateway | Channel access, session routing, adapter | Yes |
| models.providers | HTTP interface, capability negotiation | Yes |
| bridge | Protocol translation, session mapping | Yes |
| claude-node | Runtime management, event streams | Yes |
| Claude Code CLI | Autonomous agent execution | Yes |
| DB/Control Plane | State persistence, source of truth | Yes |
| Notifier | Outbound Feishu updates | Yes |

**Observations:**
- No layer appears to be doing work that should belong to another layer
- The bridge is appropriately thin — it translates, not computes
- Gateway correctly remains "adapter only" without business logic
- Control plane externalization prevents state loss across session boundaries

---

## Design Quality

### Strengths

1. **Aligns with OpenClaw's intended architecture**: Using `models.providers` instead of `cliBackends` respects OpenClaw's design intent — providers are first-class citizens, CLI backends are fallbacks.

2. **Clear separation of concerns**: Each layer has exactly one primary responsibility. The bridge translates, claude-node runs, Control Plane persists, Notifier notifies.

3. **Enables full Claude Code capabilities**: By using the HTTP provider path, the architecture unlocks tools, streaming, and OpenClaw tool integrations that are disabled in cliBackends mode.

4. **Session persistence via Control Plane**: Externalizing run_id and stage tracking to a database enables proper long-running conversation support and auditability.

5. **Minimal wrapper.py concerns**: The architecture acknowledges that wrapper.py currently has overloaded responsibilities and properly addresses this by introducing a dedicated bridge layer.

### Weaknesses

1. **Bridge resilience not specified**: The proposed architecture does not address how the bridge handles:
   - claude-node restarts or crashes
   - Network failures between bridge and claude-node
   - Connection pooling for concurrent requests

2. **Control Plane becomes a single point of failure**: If the DB/Control Plane is unavailable, the architecture has no fallback strategy documented.

3. **Notifier coupling**: The architecture shows Feishu Notifier at the bottom but does not specify how it receives events. If it polls the Control Plane, there's a polling overhead problem. If it receives push events, the event channel is unspecified.

---

## Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Bridge resilience | MEDIUM | No explicit plan for bridge fault tolerance (retries, circuit breakers, health checks) |
| Control Plane SPOF | MEDIUM | DB/Control Plane is critical path but no HA/fallback strategy documented |
| Event channel ambiguity | LOW | Notifier → Feishu event delivery mechanism unspecified (push vs poll) |
| Session migration | LOW | No plan for migrating sessions if claude-node needs to move to different host |

---

## Recommendation

**Accept the architecture with the following enhancements:**

1. **Bridge resilience**: Add explicit health check endpoint and retry logic to the bridge design. Consider a simple circuit breaker pattern.

2. **Control Plane fallback**: Define a degraded mode — if Control Plane is unavailable, can the system continue with in-memory state (accepting that some features like card updates will be disabled)?

3. **Clarify event delivery**: Specify whether the Notifier uses:
   - WebSocket push from Control Plane
   - Polling interval
   - Webhook callback to Feishu

4. **Document session lifecycle**: Define what happens to `run_id → feishu_context` mappings when claude-node process restarts.

Overall, the architecture is **fundamentally sound** and represents a correct understanding of OpenClaw's design philosophy. The identified issues are refinements rather than structural problems.
