# Improvement Directions Review

## Verdict: PARTIAL

## Current Plan Summary

The current daemon-pool plan proposes:
1. Transform wrapper.py into an HTTP daemon server (port 18790)
2. Implement a session pool (max 10 ClaudeController instances) with LRU eviction
3. Add `/chat` and `/health` endpoints
4. Change OpenClaw config from `input: arg` to `input: http`

**Critical flaw**: The plan assumes OpenClaw supports `input: http` for cliBackends. Research confirms OpenClaw only supports `input: arg` and `input: stdin` — the entire HTTP daemon integration via cliBackends is impossible.

---

## Improvement Opportunities

### 1. Multi-Provider Fallback Chain

**Not considered**: Currently only one cliBackends entry exists. A proper fallback chain could:
- Primary: `models.providers` → bridge (full capability)
- Fallback: `cliBackends` → wrapper.py (text-only, current production path)

**Benefit**: Zero-downtime migration from cliBackends to bridge.

### 2. Bridge Service Without Full Session Pool

**Not considered**: The session pool (10 controllers, LRU eviction) adds significant complexity. A simpler approach:
- Stateless bridge: each request spawns/gets a session from claude-node
- Let claude-node handle session lifecycle internally

**Benefit**: Eliminates daemon-pool's most complex component. Pool management is claude-node's job, not bridge's.

### 3. Streaming Support via models.providers

**Not considered**: cliBackends is explicitly "text-only fallback" — no streaming, no tools, no skills. models.providers with `api: "openai-completions"` supports streaming natively.

**Missing**: No plan to enable streaming to Feishu cards.

### 4. Health Check and observability

**Not considered**: No metrics, no structured logging, no request tracing across the full chain:
- Feishu → Gateway → provider/bridge → claude-node → Claude CLI
- No `run_id` propagation for debugging

### 5. Graceful Degradation

**Not considered**: What happens when bridge is down? When claude-node is slow? When Claude CLI fails?
- No circuit breaker
- No timeout strategy
- No retry backoff

---

## Alternative Approaches

### Approach A: Bridge as models.providers (Recommended)

```
OpenClaw Gateway → models.providers → bridge (HTTP) → claude_node → Claude CLI
```

- Bridge implements `/v1/chat/completions` (OpenAI-compatible)
- Use `api: "openai-completions"` for streaming support
- cliBackends remains as fallback
- **Session pool logic stays inside claude_node**, not in bridge

**Pros**: Full tool support, streaming, proper provider protocol
**Cons**: Need to implement bridge HTTP server

### Approach B: Enhanced cliBackends Wrapper

Keep cliBackends but enhance wrapper.py:
- Pre-warm one or more ClaudeController instances
- Use `input: stdin` mode for structured JSON passing
- Not full HTTP, but persistent subprocess

**Pros**: Minimal change, leverages existing architecture
**Cons**: Still text-only, no tools/streaming, architecture smell (using fallback as primary)

### Approach C: Hybrid

1. Keep cliBackends for commands/single-shot
2. Add models.providers for full conversations
3. OpenClaw routes based on model selection

**Pros**: Best of both worlds
**Cons**: More complex configuration

---

## Evolution Path

### Phase 1: Minimal Viable Bridge
```
bridge.py (new) → claude_node → Claude CLI
                ↑
OpenClaw models.providers (HTTP)
```

1. Implement bridge with `/v1/chat/completions`
2. Add to openclaw.json as new provider
3. Test with single model ref
4. Keep cliBackends as fallback

### Phase 2: Session Persistence
- Leverage claude-node's existing session management
- Pass `conversation_id` through to claude-node
- Remove wrapper.py cold-start overhead

### Phase 3: Full Streaming
- Enable streaming on provider
- Implement Feishu card updates via stage events
- Add run_id tracking

### Phase 4: Observability
- Structured logging with request IDs
- Metrics: latency, error rate, pool size
- Health endpoint on bridge

---

## Issues Found

1. **daemon-pool is architecturally incompatible** with OpenClaw's cliBackends protocol (confirmed: only `arg` and `stdin` inputs)

2. **Session pool complexity misplaced** — pool should live in claude-node or be stateless in bridge, not require a special HTTP daemon mode

3. **No migration path** — current plan has no strategy for transitioning from cliBackends to models.providers without downtime

4. **Performance assumptions unverified** — 5-30 second cold start cited as motivation, but no measurement of actual current latency

---

## Recommendation

**Priority 1 — Fix architecture**:
- Abandon `input: http` assumption
- Redirect daemon-pool effort to bridge + models.providers
- Session pool logic (if needed) belongs in claude-node, not as separate daemon

**Priority 2 — Incremental delivery**:
- Bridge first (stateless HTTP, single /chat endpoint)
- Verify latency improvement before adding pool complexity
- Add streaming in separate phase

**Priority 3 — Architecture clarity**:
- Document the correct layered architecture
- Update CLAUDE.md with proper component boundaries
- Clarify that cliBackends is intentional fallback, not primary path
