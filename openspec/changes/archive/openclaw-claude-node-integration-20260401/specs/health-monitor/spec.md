## ADDED Requirements

### Requirement: Health Monitoring
The Bridge Server SHALL continuously monitor claude-node's health status.

### Requirement: Periodic Health Check
The Health Monitor SHALL check claude-node status every 30 seconds (configurable).

#### Scenario: Detect claude-node disconnection
- **WHEN** claude-node fails to respond to a health check
- **THEN** Health Monitor SHALL mark claude_node status as "disconnected"
- **AND** SHALL set overall status to "unhealthy"

#### Scenario: Detect claude-node reconnection
- **WHEN** claude-node recovers and responds to health check
- **THEN** Health Monitor SHALL mark claude_node status as "connected"
- **AND** SHALL set overall status to "healthy"

### Requirement: Health Status API
Health status SHALL be exposed via GET /health endpoint.

#### Scenario: Return healthy status
- **WHEN** All components are operational
- **THEN** GET /health SHALL return status code 200
- **AND** body SHALL be `{"status": "healthy", "claude_node": "connected", "timestamp": "..."}`

#### Scenario: Return unhealthy status
- **WHEN** claude-node is disconnected
- **THEN** GET /health SHALL return status code 503
- **AND** body SHALL be `{"status": "unhealthy", "claude_node": "disconnected", "timestamp": "..."}`

### Requirement: Fallback Trigger
When health status becomes unhealthy, the system SHALL notify OpenClaw to activate fallback mode.
