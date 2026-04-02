## ADDED Requirements

### Requirement: CLAUDE.md reflects actual runtime architecture
The `CLAUDE.md` file SHALL accurately describe the current production architecture as:
- OpenClaw Gateway (Node.js, port 18789) as IM bridge layer
- `cliBackends.claude-node-cli` with `input:arg` mode as AI engine routing
- `claude-node-cli-wrapper.py` (Python) as CLI wrapper
- `claude-node` Python package as Claude Code CLI wrapper
- Claude Code CLI as the execution kernel

The document SHALL indicate the previous `clawrelay-feishu-server` approach as deprecated.

#### Scenario: CLAUDE.md matches production
- **WHEN** a new developer reads `CLAUDE.md`
- **THEN** they can understand how messages flow from Feishu through to Claude Code CLI and back
