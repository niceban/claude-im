## Why

The project currently has conflicting architecture narratives, duplicated solution paths, and stale AI-generated working notes spread across the standards repo and external workspaces. This makes it unclear which runtime path, backend entry point, and feature status are authoritative, and it blocks consistent implementation and maintenance.

## What Changes

- Establish a single canonical documentation baseline for the project.
- Standardize the runtime path as `clawrelay-feishu-server -> claude-node -> Claude Code CLI`.
- Standardize the admin/reporting product as `clawrelay-report`, with `http://localhost:5173` as the only user-facing backend/admin entry.
- Remove or rewrite conflicting documentation, legacy design notes, and hidden AI process artifacts that describe deprecated paths.
- Remove parallel chat/SSE execution surfaces from the reporting and auxiliary API layers until they are explicitly reintroduced through a verified change.
- Reframe unverified capabilities, especially SSE, as unconfirmed rather than implemented.

## Capabilities

### New Capabilities
- `project-standard-governance`: Defines how the project records its authoritative architecture, backend entry point, documentation hierarchy, and feature verification status.

### Modified Capabilities

## Impact

- Affected repositories and workspaces:
  - `/Users/c/claude-im`
  - `/Users/c/clawrelay-feishu-server`
  - `/Users/c/clawrelay-report`
- Affected systems:
  - standards and documentation
  - admin/reporting backend exposure
  - auxiliary SSE/chat execution entry points
- Affected behavior:
  - `http://localhost:5173` becomes the sole user-facing admin entry
  - `8000` is treated as internal API only
  - deprecated `clawrelay-api` and parallel SSE narratives are removed from active project guidance
