## ADDED Requirements

### Requirement: Fallback Manager
The Fallback Manager SHALL coordinate the activation and deactivation of OpenClaw fallback mode when claude-node goes down or recovers.

### Requirement: Fallback Activation
When claude-node is unhealthy, the system SHALL activate OpenClaw fallback mode.

#### Scenario: Activate fallback on claude-node failure
- **WHEN** Health Monitor reports claude_node status as "disconnected"
- **THEN** Fallback Manager SHALL set state to FALLBACK
- **AND** SHALL notify OpenClaw to activate

### Requirement: OpenClaw Repair Mode
When in fallback mode, OpenClaw SHALL only execute repair tasks (restarting claude-node).

#### Scenario: Execute repair
- **WHEN** OpenClaw is in fallback mode
- **THEN** OpenClaw Skill SHALL attempt to restart claude-node service
- **AND** SHALL verify recovery via health check

### Requirement: Fallback Deactivation
When claude-node recovers, the system SHALL deactivate fallback mode and resume normal operation.

#### Scenario: Deactivate fallback on recovery
- **WHEN** Health Monitor reports claude_node status as "connected"
- **THEN** Fallback Manager SHALL set state to NORMAL
- **AND** SHALL notify OpenClaw to deactivate

### Requirement: Fallback State Machine
The Fallback Manager SHALL implement the following state machine:
- **NORMAL**: claude-node is healthy, OpenClaw is silent
- **FALLBACK**: claude-node is unhealthy, OpenClaw is active for repairs

#### State Transition: NORMAL → FALLBACK
- **WHEN** Health check fails 3 consecutive times
- **THEN** State SHALL transition to FALLBACK

#### State Transition: FALLBACK → NORMAL
- **WHEN** Health check succeeds 3 consecutive times
- **THEN** State SHALL transition to NORMAL
