## Context

The project was carrying multiple overlapping architecture stories at the same time:

- a legacy `clawrelay-api` path
- a direct `claude-node` path
- a Grafana-oriented observability/admin narrative
- a `clawrelay-report` full-stack admin narrative
- unverified SSE/chat-stream implementations and notes that were being described as if they were part of the active baseline

These inconsistencies existed across the standards repository and the external workspaces that actually implement the system. The result was that different files described different runtime paths, different backend entry points, and different feature readiness assumptions.

This change is cross-cutting because it spans:

- the standards repository
- the Feishu adapter workspace
- the report/admin workspace

## Goals / Non-Goals

**Goals:**

- Define one authoritative project narrative and one documentation hierarchy.
- Make the runtime path explicit: `clawrelay-feishu-server -> claude-node -> Claude Code CLI`.
- Make the admin/reporting path explicit: `clawrelay-report`, with `http://localhost:5173` as the only user-facing admin entry.
- Remove code and documentation surfaces that create a parallel chat execution or SSE narrative.
- Convert uncertain capability language into explicit “unverified” status.

**Non-Goals:**

- Implement or verify SSE.
- Redesign the report UI or reporting data model.
- Replace Prometheus-based metrics collection where it already exists as internal telemetry.
- Normalize every historical template artifact in upstream-derived files if it does not affect the current authoritative path.

## Decisions

### 1. Use documentation governance as a first-class capability

Decision:
- Treat “project standard governance” as an explicit capability, not an informal cleanup.

Rationale:
- The root problem is not a single bug but conflicting authority. Turning this into a capability creates stable requirements for future cleanup and prevents reintroduction of parallel narratives.

Alternative considered:
- Keep this as an ad hoc repo cleanup without spec coverage.

Why rejected:
- That would solve the current mess once, but it would not define what counts as compliant documentation or backend exposure going forward.

### 2. Declare `http://localhost:5173` as the only user-facing admin entry

Decision:
- All user-facing admin/backend language must point to `http://localhost:5173`.
- `http://localhost:8000` is documented only as an internal API endpoint for the frontend and development workflows.

Rationale:
- The main ambiguity users kept encountering was whether `8000`, `5173`, Grafana, or another service counted as “the backend”. This decision removes that ambiguity.

Alternative considered:
- Allow both `5173` and `8000` to remain documented as parallel backend entry points.

Why rejected:
- It keeps the same confusion alive and weakens the concept of a single standard.

### 3. Remove parallel chat-stream/SSE execution surfaces instead of leaving them dormant

Decision:
- Delete route registrations, files, and UI entry points that expose chat-stream/SSE behavior in `clawrelay-report` and `clawrelay-feishu-server`.

Rationale:
- Leaving these in place but undocumented still creates real architectural drift. If the code exists and is discoverable, it will be treated as supported sooner or later.

Alternative considered:
- Keep the files but mark them deprecated in comments.

Why rejected:
- The current issue was caused partly by stale or hidden artifacts continuing to shape understanding. Deletion is more reliable than soft deprecation here.

### 4. Keep `clawrelay-report` read-only with respect to live chat execution

Decision:
- The report system should read and present real data, not start new chat execution flows or append chat records as a side effect of admin actions.

Rationale:
- The report system is the unique admin UI, not a second orchestration layer. This keeps the runtime path singular and preserves clear responsibility boundaries.

Alternative considered:
- Allow the report backend to support chat send/resume as an operational convenience.

Why rejected:
- That creates a second execution path and reintroduces exactly the kind of architectural fork this change is eliminating.

## Risks / Trade-offs

- [Deleting unverified SSE/chat-stream paths may remove work-in-progress experiments] → Keep the decision in spec artifacts so future reintroduction happens intentionally and through a new change.
- [External workspaces still contain unrelated uncommitted work] → Limit cleanup to items that directly conflict with the new standard; avoid broad repo normalization in the same pass.
- [Template residue may remain in low-priority files] → Prioritize user-facing and architecture-shaping files first; treat remaining template cleanup as follow-up work unless it changes authority.
- [Read-only report backend reduces flexibility for future operator tooling] → If operator-triggered chat actions are needed later, introduce them as a separate explicitly approved capability.

## Migration Plan

1. Create a canonical standard in `/Users/c/claude-im`.
2. Align entry-point docs and agent instructions to the standard.
3. Remove hidden notes and legacy docs in the standards repo.
4. Remove conflicting SSE/chat-stream routes and UI affordances from external workspaces.
5. Rewrite external workspace docs so they describe the same runtime and backend entry story.
6. Validate the resulting tree for conflicting terms such as `clawrelay-api`, `50009`, `chat-stream`, and dual backend entry language.

Rollback:
- Revert the file deletions and route removals if the project explicitly decides to restore a parallel path.
- Any restored capability must then be documented through a new OpenSpec change rather than by restoring stale notes alone.

## Open Questions

- Whether Prometheus terminology in `clawrelay-feishu-server` should remain purely internal or also be reduced in user-facing docs.
- Whether the remaining template-oriented files in `clawrelay-report` such as contribution and deployment guides should be fully rewritten now or handled in a follow-up normalization change.
