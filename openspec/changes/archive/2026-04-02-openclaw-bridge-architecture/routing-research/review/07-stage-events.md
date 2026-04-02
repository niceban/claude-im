# Stage Event Notification Review

## Verdict: PARTIALLY_SOUND

## Event Schema

**Proposed events** (from ARCHIVE.md architecture):
- `stage.started` — Agent execution phase begins
- `stage.completed` — Agent execution phase ends successfully
- `stage.failed` — Agent execution phase ends with error
- `artifact.created` — Output artifact generated
- `run_id` — Unique identifier for the execution run
- `feishu_context` — Feishu message/card reference for outbound updates

**Flow**:
```
claude-node → on_message events → DB/Control Plane (source of truth)
                                           ↓
                                    Notifier
                                           ↓
                                    Feishu Card (progressive update)
```

## Notification Flow

1. **Event Generation**: `claude-node` emits `on_message` events during execution
2. **Event Capture**: `bridge` intercepts and extracts stage events from the event stream
3. **Persistence**: `DB/Control Plane` stores `run_id → feishu_context` mapping + event history
4. **Notification**: `Notifier` reads from DB and sends stage updates to Feishu cards
5. **Card Update**: Single Feishu card progressively updated (not multiple messages)

## Key Challenges

### 1. run_id → feishu_context Mapping

**Problem**: The mapping must survive process restarts and be queryable by Notifier.

**Proposed solutions**:
- Store in DB: `run_id` (UUID), `feishu_context` (card_id + thread_id + chat_id), `created_at`, `status`
- Bridge creates `run_id` at request start, stores mapping before returning to Gateway
- Feishu plugin stores `feishu_context` when it creates the outbound card

**Risk**: If Gateway and Notifier are decoupled, mapping must be written before Gateway returns response to Feishu. This introduces a race condition if Gateway does not wait for the DB write.

### 2. Notifier Pattern Implementation

**Problem**: Notifier must reliably deliver events without duplicating or losing updates.

**Design questions**:
- Polling vs push: Does Notifier poll DB, or does it receive push events from bridge?
- Delivery guarantee: At-least-once vs at-most-once? Feishu card updates are idempotent (PUT same content = no-op).
- Ordering: Events must be applied in sequence. `stage.started` must appear before `stage.completed`.

**Recommendation**: Use event sourcing — store ordered event log in DB, Notifier reads and applies sequentially. Use `last_event_id` cursor for recovery.

### 3. OpenClaw Compatibility

**Problem**: cliBackends does not support streaming events. Only `models.providers` + bridge path supports `supportsTools: true` and streaming.

**Impact on stage events**:
- Current production (cliBackends): No stage events possible — text-only fallback
- Correct architecture (models.providers): Full event stream available

**Without tools/streaming, there is no mechanism to emit stage events from claude-node through OpenClaw.**

## Feasibility Assessment

| Component | Feasibility | Risk |
|-----------|-------------|------|
| Event schema definition | ✅ Feasible | Low |
| run_id → feishu_context DB mapping | ✅ Feasible | Medium (timing) |
| Notifier polling DB | ✅ Feasible | Low |
| Single card progressive update | ✅ Feasible | Medium (Feishu API) |
| Event ordering guarantee | ⚠️ Complex | Medium |
| Reconnection / resume | ⚠️ Needs design | High |

## Issues Found

### Issue 1: No Event Schema Defined

The documents mention `stage.started`, `stage.completed`, `stage.failed` but no concrete JSON schema is provided. Critical fields missing:

- `run_id` (required for mapping)
- `timestamp` (required for ordering)
- `stage_name` (what phase? "planning", "coding", "review"?)
- `metadata` (token usage, model used, etc.)

### Issue 2: Timing Race in run_id Creation

Bridge creates `run_id`, stores mapping, then returns to Gateway. If Gateway returns to Feishu before DB write completes, Notifier will not find the mapping. The architecture must enforce "write mapping before first response."

### Issue 3: cliBackends Cannot Support Stage Events

Current production uses cliBackends (`output: json`). This is explicitly a text-only fallback. **Stage events cannot be implemented on the current production path.** The P0 architecture shift to `models.providers` is a prerequisite.

### Issue 4: No Specification for Notifier Trigger

How does Notifier know a new run started? Options:
- Polling: Notifier polls DB every N seconds (simple, delay = N seconds)
- Push: Bridge calls Notifier webhook on each event (complex, lower latency)
- Hybrid: Bridge pushes to queue (Redis/SQS), Notifier consumes (recommended)

## Recommendation

### Immediate (P0)

1. **Define event schema** with TypeScript interface:
   ```typescript
   interface StageEvent {
     type: 'stage.started' | 'stage.completed' | 'stage.failed';
     run_id: string;
     stage: string;
     timestamp: number; // Unix ms
     metadata?: Record<string, unknown>;
   }
   ```

2. **Implement `run_id → feishu_context` mapping as first-class DB entity** with unique index on `run_id`.

3. **Enforce write-before-return**: Bridge DB write must complete before HTTP response is returned to Gateway.

### Short-term (P1)

4. **Choose push queue over polling**: Bridge emits events to Redis stream, Notifier consumes. This decouples and provides natural ordering.

5. **Idempotent card updates**: Use Feishu card `update` (PATCH) with `etag` handling to prevent overwrites.

### Long-term (P2)

6. **Define recovery protocol**: If Notifier crashes mid-run, it must resume from last processed `event_id`. Store `last_event_id` per `run_id`.

7. **Reconnection flow**: If Feishu client disconnects, card should remain accessible by `card_id` alone — `feishu_context` should be durable.

## Conclusion

The stage event notification scheme is **architecturally sound** in the correct `models.providers` path, but **not feasible on the current cliBackends production path**. The Notifier pattern and DB mapping approach are correct, but there are significant gaps in:

- Event schema definition
- Timing/race condition handling
- Event ordering guarantees
- Recovery/resume logic

The scheme requires P0 architecture migration (cliBackends → models.providers) before stage events can be implemented.
