## ADDED Requirements

### Requirement: HTTP Daemon Server
The daemon SHALL run as a long-running HTTP server on a configurable port (default 18790).

### Requirement: /chat Endpoint
The `/chat` endpoint SHALL accept a JSON body with the following schema:
```json
{
  "conversation_id": "string",
  "messages": [{"role": "user"|"assistant", "content": "string"}],
  "resume": boolean
}
```
SHALL return a JSON object with the result from `ClaudeController.send()`.

### Requirement: /health Endpoint
The `/health` endpoint SHALL return `{"ok": true, "pool_size": N}` where N is the current number of active controllers in the pool.

### Requirement: Port Configuration
The daemon port SHALL be configurable via `CLAUDE_DAEMON_PORT` environment variable, defaulting to `18790`.

### Requirement: Startup Validation
On startup, the daemon SHALL run `validate_config()` before accepting requests. If validation fails, the daemon SHALL exit with a non-zero code and write error details to stderr.

#### Scenario: Successful startup
- **WHEN** daemon process starts with valid configuration
- **THEN** it binds to the configured port and begins accepting HTTP requests

#### Scenario: Invalid configuration on startup
- **WHEN** daemon starts but configuration validation fails
- **THEN** it writes error to stderr and exits with code 1

#### Scenario: /health returns pool status
- **WHEN** GET /health is received
- **THEN** daemon returns `{"ok": true, "pool_size": N}` with HTTP 200
