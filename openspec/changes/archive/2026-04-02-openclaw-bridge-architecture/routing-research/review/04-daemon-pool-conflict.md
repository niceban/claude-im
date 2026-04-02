# daemon-pool Conflict Review

## Verdict: ACCURATELY_IDENTIFIED

## The Design Assumption

daemon-pool design assumed OpenClaw supports an `input: http` mode for cliBackends, allowing:

```
OpenClaw cliBackends (input: http) → daemon HTTP server (port 18790) → claude_node session pool
```

Specifically:
- **proposal.md line 14**: `BREAKING: OpenClaw 配置变更: input: arg → input: http`
- **design.md line 21**: References "OpenClaw cliBackends HTTP 模式" as if it existed but just didn't support streaming
- **design.md Decision 5**: Describes HTTP mode input parsing as a feature to remove

The daemon.py was fully implemented as an HTTP server (`/chat` + `/health` endpoints, port 18790, session pool with LRU), but it can never be called by OpenClaw.

## The Reality

**OpenClaw CliBackendSchema** (from `zod-schema.core.ts`):
```typescript
input: z.union([z.literal("arg"), z.literal("stdin")]).optional()
```

Only two input modes exist:
1. **`arg`**: Passes prompt as the last CLI argument (current production mode)
2. **`stdin`**: Sends prompt via standard input stream as JSON

**There is no `http` mode.** This is confirmed by:
- Multiple research findings citing the actual OpenClaw source schema
- wrapper.py only implements arg/stdin parsing (lines 78-111)
- daemon.py is a complete HTTP server that has no path to integration with OpenClaw

The correct HTTP integration path is via `models.providers`, not `cliBackends`:
```
OpenClaw models.providers (HTTP) → bridge HTTP → claude_node
```

## Conflict Analysis

**The conflict is correctly identified.** The evidence chain is solid:

| Evidence | Source | Credibility |
|----------|--------|-------------|
| Schema only has arg/stdin | OpenClaw `zod-schema.core.ts` | High (source code) |
| daemon.py HTTP server cannot be called | daemon.py + schema constraint | High |
| wrapper.py only handles arg/stdin | wrapper.py lines 63-111 | High |

The conflict-summary.md accurately maps:
- What daemon-pool assumed (`input: http`)
- Why it's impossible (schema constraint)
- What the correct approach is (models.providers)

## Root Cause

daemon-pool designers confused two distinct OpenClaw integration points:
- **cliBackends**: stdin/arg only, short-lived process per request
- **models.providers**: HTTP, long-running server, proper API protocol

They designed a session pool daemon with HTTP interface but tried to attach it to cliBackends, which has no HTTP capability.

## Issues Found

**No issues with the conflict analysis itself.** However, there is one incomplete aspect:

The design Non-Goals state (design.md line 21):
> "不实现 WebSocket 流式（当前 OpenClaw cliBackends HTTP 模式不支持）"

This implies the designers thought HTTP mode *might* exist but just didn't support streaming. The more accurate framing is: **HTTP mode does not exist at all in cliBackends**. The Non-Goals should have been "不实现 WebSocket 流式（OpenClaw cliBackends 不支持 HTTP）".

Additionally, the conflict-summary.md correctly identifies the architectural error but the recommended alternative (models.providers) is a more significant change than just fixing Phase 5 tasks. It would require a complete protocol change from CLI to HTTP API.

## Recommendation

1. **Archive daemon-pool Phase 5** - the HTTP daemon integration via cliBackends is architecturally impossible
2. **Reconsider the problem**: The actual goal is session pool hot-start, not HTTP integration
3. **Alternative approaches** (from research):
   - **stdin persistence**: Keep `input: stdin` but make wrapper long-running, reading multiple JSON objects from stdin (avoids spawn-per-request)
   - **models.providers**: Full HTTP API redesign (significant effort, enables tools/streaming)
4. **daemon.py session pool code is valuable** - it proves the pool logic works; the architecture connection is wrong, not the pool implementation
