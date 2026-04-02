# Minimum Change Plan Review

## Verdict: PARTIALLY_FEASIBLE

## Proposed Changes

**P0 (Immediate)**:
1. Implement bridge service with `/v1/chat/completions` endpoint
2. Update `openclaw.json` models.providers to point to bridge
3. Keep existing cliBackends as fallback

**P1**: Notifier, run_id mapping, daemon-pool redesign
**P2**: Cleanup deprecated config

## Feasibility Analysis

### Step-by-Step Assessment

| Step | Feasibility | Notes |
|------|-------------|-------|
| Implement bridge service | Possible | Requires new code; no existing bridge found |
| Update models.providers | Straightforward | Standard OpenClaw config; example format known |
| Keep cliBackends as fallback | Safe | Existing config can remain unchanged |

### Key Findings from Architecture Research

**cliBackends vs models.providers capability gap**:

| Capability | cliBackends (current) | models.providers (proposed) |
|------------|---------------------|----------------------------|
| tools | Not supported | Supported |
| streaming | Not supported | Supported |
| OpenClaw tools | Disabled | Enabled |
| Communication | stdin/CLI args | HTTP |

**cliBackends IS the safety-net/fallback** per official definition, not a primary path.

### Why the Plan is Feasible

1. **Orthogonal mechanisms**: models.providers and cliBackends can coexist
2. **Standard protocol**: Bridge only needs to implement `/v1/chat/completions` (OpenAI-compatible)
3. **Fallback preserved**: Existing cliBackends path continues to work if bridge fails
4. **Proven format**: Provider config format is documented and used by Ollama, Doubao, etc.

### Why the Plan is Only PARTIALLY Feasible

1. **No existing bridge implementation**: Must build from scratch; no openclaw-claude-bridge found
2. **Session mapping gap**: Bridge needs to map OpenClaw sessions to claude_node sessions
3. **P0 defers critical work**: run_id tracking and notifier are P1, but these are essential for Feishu integration
4. **daemon-pool abandonment**: The previous design is scrapped, but replacement for multi-session management is unclear

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Bridge service goes down | HIGH | cliBackends fallback exists, but is text-only (degraded capability) |
| Session state lost during fallback | HIGH | No session continuity between provider and cliBackends paths |
| Session mapping complexity underestimated | MEDIUM | claude_node session management needs careful study |
| run_id tracking deferred too long | MEDIUM | Essential for Feishu card updates; should be P0 |
| Bridge adds latency | LOW | One extra HTTP hop; acceptable for full capability |

## Complexity

**Implementation Complexity: MEDIUM**
- Bridge service: ~200-400 lines (FastAPI/Node)
- Provider config: < 20 lines JSON
- Testing: Need to verify both paths work

**Integration Complexity: HIGH**
- Session mapping between OpenClaw HTTP protocol and claude_node on_message events
- Error handling when primary (bridge) fails and falls back to cliBackends
- Need to preserve session context across fallback

**Operational Complexity: MEDIUM**
- New service to monitor (bridge process management)
- Two execution paths to debug instead of one

## Issues Found

### Issue 1: No Existing Bridge Codebase
- **Finding**: No `openclaw-claude-bridge` implementation found in `.deep-now/`
- **Impact**: P0 requires building new service from scratch
- **Action**: Clone or reference existing claude_node examples before coding

### Issue 2: Session Mapping Not Specified
- **Finding**: ARCHIVE.md doesn't specify how bridge maps OpenClaw session_id to claude_node session
- **Impact**: Critical for maintaining conversation context
- **Action**: Add session mapping design to P0 scope

### Issue 3: P0 Incomplete for Production Use
- **Finding**: Feishu integration requires run_id tracking and notifier (both P1)
- **Impact**: Even with P0 complete, cannot update Feishu messages with stage events
- **Action**: Consider moving run_id mapping to P0 or defining minimal notifier for P0

### Issue 4: cliBackends Fallback is Degraded
- **Finding**: cliBackends fallback provides text-only capability (no tools/streaming)
- **Impact**: If bridge fails in production, users get degraded experience
- **Action**: Document this limitation; plan for bridge HA/monitoring

## Recommendation

### Immediate Actions for P0

1. **Split P0 into P0a + P0b**:
   - P0a: Bridge service + models.providers config (straightforward)
   - P0b: Session mapping design (needs research)

2. **Add session mapping to P0a**:
   - Before building bridge, study how claude_node handles sessions
   - Define session_id mapping strategy
   - Document the mapping in spec before coding

3. **Define minimal notifier for P0a**:
   - Even basic notifier (no Feishu cards) enables monitoring
   - Plan for Feishu card updates in P0b

4. **Preserve cliBackends key naming**:
   - Current key `claude-node-cli` already matches provider naming
   - Keep as-is for fallback; no changes needed

### Medium-term (P1)

1. Implement run_id → feishu_context mapping
2. Implement notifier for stage events
3. Add bridge health monitoring

### Architecture Quality

The plan moves in the right direction (provider over cliBackends for primary path) but:
- Is conservative in scope (good)
- Defers critical integration work too long (risky)
- Needs more specificity on session management before coding begins
