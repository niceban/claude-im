# Routing Analysis Review

## Verdict: CORRECT

## Analysis

### 1. How OpenClaw Resolves `claude-node-cli/MiniMax-M2.7`

The model ref `claude-node-cli/MiniMax-M2.7` is parsed as:
- **Provider**: `claude-node-cli`
- **Model**: `MiniMax-M2.7`

**Resolution flow** (verified via `/opt/homebrew/lib/node_modules/openclaw/dist/model-selection-CMtvxDDg.js`):

1. `parseModelRef(raw, defaultProvider)` at line 127-136 splits on `/`:
   ```javascript
   const slash = trimmed.indexOf("/");
   if (slash === -1) return normalizeModelRef(defaultProvider, trimmed, options);
   const providerRaw = trimmed.slice(0, slash).trim();
   const model = trimmed.slice(slash + 1).trim();
   ```

2. `isCliProvider(provider, cfg)` at line 85-90 determines routing path:
   ```javascript
   function isCliProvider(provider, cfg) {
     const normalized = normalizeProviderId(provider);
     if ((loadCliBackendRuntime()?.resolveRuntimeCliBackends() ?? []).some((backend) => normalizeProviderId(backend.id) === normalized)) return true;
     const backends = cfg?.agents?.defaults?.cliBackends ?? {};
     return Object.keys(backends).some((key) => normalizeProviderId(key) === normalized);
   }
   ```

3. For `claude-node-cli`, it checks `cfg.agents.defaults.cliBackends` and finds `claude-node-cli` key → returns `true`

### 2. cliBackends vs models.providers Resolution Priority

**cliBackends and models.providers are orthogonal mechanisms**:

| Aspect | cliBackends | models.providers |
|--------|-------------|-----------------|
| Transport | stdin/CLI args | HTTP requests |
| Purpose | Local CLI agents | Cloud/local HTTP APIs |
| Schema help | "text-only fallback" | Standard provider config |

**Resolution order for provider lookup**:
1. `isCliProvider()` first checks runtime plugin cliBackends
2. Then checks `cfg.agents.defaults.cliBackends`
3. If either matches, routing goes through CLI backend path
4. HTTP providers are checked separately via `providerAuthMap`

**Evidence** from `auth-profiles-B5ypC5S-.js` line 1722:
```javascript
const missingProvidersInUse = Array.from(providersInUse)
  .filter((provider) => !providerAuthMap.has(provider))
  .filter((provider) => !isCliProvider(provider, cfg))  // CLI providers exempted
```

### 3. Current Configuration Analysis

From `~/.openclaw/openclaw.json`:

```json
"models": {
  "providers": {
    "doubao": {...},      // HTTP provider
    "minimax-cn": {...}    // HTTP provider
    // NOTE: NO "claude-node-cli" entry here
  }
},
"agents": {
  "defaults": {
    "model": {
      "primary": "claude-node-cli/MiniMax-M2.7",
      "fallbacks": ["minimax-cn/MiniMax-M2.7"]
    },
    "cliBackends": {
      "claude-node-cli": {
        "command": "python3",
        "args": ["/Users/c/claude-node-cli-wrapper-v2/wrapper.py"],
        ...
      }
    }
  }
}
```

**Conclusion**: Since `models.providers` has NO entry for `claude-node-cli`, and `cliBackends` DOES have `claude-node-cli`, the routing **must** go through cliBackends.

### 4. cliBackends "text-only fallback" Limitation

The OpenClaw schema confirms the "text-only fallback" characterization:

From `plugin-sdk/src/config/schema.base.generated.d.ts` line 13027-13029:
```typescript
readonly "agents.defaults.cliBackends": {
    readonly label: "CLI Backends";
    readonly help: "Optional CLI backends for text-only fallback (claude-cli, etc.).";
    readonly tags: ["advanced"];
}
```

**However**, the actual implementation may support more:
- `output` field supports `json`, `text`, and `jsonl` (streaming) modes
- wrapper.py environment has `CLAUDE_TOOLS` set
- `CLAUDE_STREAM_EVENTS: "false"` suggests streaming IS supported but controlled

The "text-only" label in schema may refer to the OpenClaw agent/tools integration being limited, not the underlying CLI capabilities.

## Evidence

| Source | Location | Finding |
|--------|----------|---------|
| model-selection-CMtvxDDg.js:85-90 | `isCliProvider()` | Checks cliBackends keys for routing |
| auth-profiles-B5ypC5S-.js:1722 | Missing provider check | CLI providers exempted from provider auth |
| auth-profiles-B5ypC5S-.js:214892 | `resolveCliBackendConfig()` | Falls back to cfg cliBackends |
| schema.base.generated.d.ts:13027 | CLI Backends help | "text-only fallback" |
| openclaw.json:25-49 | providers config | No `claude-node-cli` entry |
| openclaw.json:59-83 | cliBackends config | `claude-node-cli` entry exists |

## Issues Found

### Issue 1: Schema Says "text-only" but wrapper.py Claims Full Features

**Severity**: Medium

The OpenClaw schema describes cliBackends as "text-only fallback" but wrapper.py appears to support:
- Tools via `CLAUDE_TOOLS` env var
- Streaming via JSONL output

This is a **documentation inconsistency** rather than a routing error. The actual behavior depends on whether OpenClaw's agent framework passes tool definitions to CLI backends.

### Issue 2: Routing Is Correct But Architecture Is Suboptimal

**Severity**: Low (informational)

The archive correctly identifies that:
- Current routing goes through cliBackends (text-only fallback path)
- `models.providers.claude-node-cli` doesn't exist (no HTTP provider path)
- This means full OpenClaw features (tools, streaming integration) may not work

This is a **design choice**, not a bug. The wrapper implements its own tool handling.

## Recommendation

The archive's routing analysis is **CORRECT** and can be used as-is. The key findings:

1. `claude-node-cli/MiniMax-M2.7` routes through `cliBackends.claude-node-cli`
2. `models.providers` has no `claude-node-cli` entry - this is intentional
3. The "text-only fallback" characterization in schema may be conservative

No changes needed to the archive's routing conclusions.