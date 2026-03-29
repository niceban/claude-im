## ADDED Requirements

### Requirement: HTTP Server
The Bridge Server SHALL expose an HTTP server on port 18792 that wraps claude-node with an OpenAI-compatible API.

### Requirement: POST /v1/chat/completions (Blocking v1)
The Bridge SHALL accept chat completions requests in OpenAI format and return blocking responses (no streaming for v1).

#### Scenario: Blocking chat completion
- **WHEN** POST /v1/chat/completions is called with `{"model": "claude-sonnet-4-6", "messages": [...]}`
- **THEN** Bridge SHALL call claude-node's blocking `send()` method
- **AND** SHALL return response in OpenAI chat completion format

### Requirement: GET /health
The Bridge SHALL expose a health check endpoint.

#### Scenario: Health check returns healthy
- **WHEN** GET /health is called
- **THEN** Bridge SHALL return `{"status": "healthy", "claude_node": "connected"}`

#### Scenario: Health check returns unhealthy
- **WHEN** GET /health is called and claude-node is not responding
- **THEN** Bridge SHALL return `{"status": "unhealthy", "claude_node": "disconnected"}`

### Requirement: GET /v1/models
The Bridge SHALL return a list of available models in OpenAI format.

#### Scenario: Models list
- **WHEN** GET /v1/models is called
- **THEN** Bridge SHALL return `{"object": "list", "data": [{"id": "claude-sonnet-4-6", ...}]}`

### Requirement: Session Management
The Bridge SHALL use session_mapping table to map OpenClaw sessions to claude-node sessions.

#### Scenario: Create new session mapping
- **WHEN** First message from a new OpenClaw session arrives
- **THEN** Bridge SHALL create a new claude-node session
- **AND** SHALL store the mapping in session_mapping table

#### Scenario: Route message to existing session
- **WHEN** Message arrives for an existing OpenClaw session
- **THEN** Bridge SHALL look up the claude_session_id from session_mapping
- **AND** SHALL route the message to the correct claude-node session
