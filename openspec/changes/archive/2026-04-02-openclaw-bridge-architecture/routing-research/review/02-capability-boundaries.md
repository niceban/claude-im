# Capability Boundaries Review

## Verdict: PARTIALLY_ACCURATE

## cliBackends Capabilities

**Claimed**: "text-only fallback", "tools disabled, no streaming"

**Actual capabilities based on code analysis**:

1. **Tools support**: cliBackends CAN support tools
   - wrapper.py line 246: `tools=cfg.claude_tools if cfg.claude_tools else None` passed to ClaudeController
   - Production config: `CLAUDE_TOOLS: "Bash,Read,Write,Glob,Grep,WebFetch,Agent,Task,TaskOutput,TodoWrite,Edit,Search"`
   - Tools are NOT inherently disabled by cliBackends protocol

2. **Streaming support**: cliBackends CAN support streaming
   - wrapper.py has full `on_message` callback handling: `assistant`, `tool_use`, `tool_result`, `system/task_*` events
   - `write_event()` outputs JSONL to stdout
   - Default config: `CLAUDE_STREAM_EVENTS: "true"`
   - Production config: `CLAUDE_STREAM_EVENTS: "false"` (explicitly disabled)

3. **Input modes**: Only `arg` and `stdin` are supported (confirmed by E1)
   - Schema: `z.union([z.literal("arg"), z.literal("stdin")])`
   - `input: http` does NOT exist

**The "text-only" characterization is INCORRECT** as a general statement about cliBackends. The wrapper itself supports tools and streaming. The production deployment disables streaming via config, not due to protocol limitations.

## models.providers Capabilities

**Claimed**: Supports tools/streaming

**Actual capabilities**:
- HTTP-based (OpenAI-compatible `/v1/chat/completions`)
- Supports streaming via SSE
- Standard tools API via function calling

**The conclusion that models.providers supports tools/streaming while cliBackends does not is MISLEADING**:
- The DIFFERENCE is not capability but PROTOCOL
- cliBackends: subprocess-based, JSONL streaming events via stdout
- models.providers: HTTP-based, SSE streaming

## Key Finding

The "text-only fallback" characterization conflates two separate issues:

1. **Protocol limitation**: cliBackends uses stdout for streaming (JSONL), while OpenClaw's `output: "json"` mode expects single JSON object. This causes parse failures with streaming enabled.

2. **Configuration choice**: Production sets `CLAUDE_STREAM_EVENTS: "false"` as workaround, making output "text-only" by disabling streaming features.

The root cause is a **protocol mismatch** (JSONL vs JSON output expectations), NOT an inherent cliBackends capability limitation.

## Evidence

| Source | Finding |
|--------|---------|
| wrapper.py lines 124-168 | Full streaming event support via `on_message` callback |
| wrapper.py line 246 | Tools passed to ClaudeController |
| config.py line 21 | Default `CLAUDE_STREAM_EVENTS = "true"` |
| openclaw.json line 79 | Production `CLAUDE_STREAM_EVENTS: "false"` |
| evidence-index.md E1 | `input: z.union([z.literal("arg"), z.literal("stdin")])` - no http mode |
| root-cause.md line 56-57 | Claims "tools disabled, no streaming" |

## Issues Found

1. **Mischaracterization**: The claim "tools disabled" is factually incorrect. Tools are enabled in production config.

2. **Confusion of cause**: The archive treats streaming as inherently impossible via cliBackends, when it's actually disabled by configuration choice to work around output format mismatch.

3. **The actual blocker**: The issue is `output: "json"` expecting single JSON, while wrapper outputs JSONL. This is a solvable problem (use `output: "jsonl"` or fix wrapper output format), not a fundamental capability gap.

## Recommendation

1. **Revise characterization**: cliBackends is NOT inherently "text-only" or "tools disabled". It supports full Claude Code capabilities.

2. **Correct the issue statement**: The real issue is output format compatibility (JSONL vs JSON), not capability boundaries.

3. **Consider re-enabling streaming**: If wrapper output format is fixed to match OpenClaw expectations, streaming can be re-enabled without switching to models.providers.
