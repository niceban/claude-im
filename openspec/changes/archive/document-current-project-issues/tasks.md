## 1. Standards Repository Alignment

- [x] 1.1 Create and maintain a single canonical standard document in `/Users/c/claude-im`
- [x] 1.2 Align `README.md` and `AGENTS.md` to the canonical standard and remove conflicting architecture statements
- [x] 1.3 Remove hidden AI notes, deprecated architecture docs, and duplicate narrative files from the standards repository
- [x] 1.4 Verify the standards repo no longer presents `clawrelay-api`, dual backend entry points, or confirmed SSE language as active baseline

## 2. Feishu Runtime Path Cleanup

- [x] 2.1 Remove legacy design notes in `/Users/c/clawrelay-feishu-server` that describe `clawrelay-api` as the active runtime path
- [x] 2.2 Remove auxiliary API or SSE/chat-stream surfaces in `/Users/c/clawrelay-feishu-server` that create a parallel execution path
- [x] 2.3 Update Feishu-side config templates and user-facing docs so they describe direct `claude-node` integration only
- [x] 2.4 Verify the Feishu workspace no longer documents `clawrelay-api`, `50009`, or chat-stream routes as active features

## 3. Report/Admin Path Cleanup

- [x] 3.1 Remove chat send/resume and SSE route exposure from `/Users/c/clawrelay-report` backend
- [x] 3.2 Remove frontend UI affordances in `/Users/c/clawrelay-report` that depend on the deleted parallel chat execution path
- [x] 3.3 Reduce report backend integrations to read-only data access for real reporting/admin use cases
- [x] 3.4 Rewrite report workspace docs and visible titles so they identify `http://localhost:5173` as the sole user-facing admin entry and `8000` as internal API only

## 4. Validation And Residual Drift Check

- [x] 4.1 Search all affected workspaces for conflicting terms such as `clawrelay-api`, `50009`, `chat-stream`, and dual backend entry wording
- [x] 4.2 Confirm SSE is described as unverified wherever it still appears in active project guidance
- [x] 4.3 Review remaining template residue and record any low-priority follow-up cleanup that does not block the canonical architecture
