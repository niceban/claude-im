# tdd-test-suite

## ADDED Requirements

### Requirement: Unit tests for each module
The system SHALL have unit tests for each module before integration.

#### Scenario: openai-compatible-api tests
- **WHEN** implementing `/v1/chat/completions` endpoint
- **THEN** tests SHALL verify request parsing, response formatting, and error handling

#### Scenario: claude-node-adapter tests
- **WHEN** implementing HTTP to ClaudeController conversion
- **THEN** tests SHALL verify format conversion and error propagation

#### Scenario: session-mapping tests
- **WHEN** implementing session mapping
- **THEN** tests SHALL verify LRU eviction, session reuse, and cleanup

### Requirement: Integration tests between modules
The system SHALL have integration tests verifying module interactions.

#### Scenario: Bridge to claude-node integration
- **WHEN** bridge receives HTTP request
- **THEN** integration test SHALL verify request reaches claude-node and response is formatted correctly

### Requirement: TDD workflow enforcement
Each module MUST have passing tests before the next module is started.

#### Scenario: Module dependency
- **WHEN** openai-compatible-api tests pass
- **THEN** claude-node-adapter development SHALL begin

### Requirement: End-to-end tests
The system SHALL have E2E tests verifying full request flow.

#### Scenario: Feishu to Claude CLI E2E
- **WHEN** test sends request through OpenClaw Gateway to bridge to claude-node
- **THEN** E2E test SHALL verify complete response chain
