# claude-node-adapter

## ADDED Requirements

### Requirement: HTTP request to ClaudeController conversion
The adapter SHALL convert OpenAI-compatible HTTP request format to claude-node ClaudeController `send()` format.

#### Scenario: Convert messages to prompt
- **WHEN** adapter receives chat messages array
- **THEN** adapter SHALL convert to a single prompt string preserving user message content

#### Scenario: Extract model ID
- **WHEN** adapter receives request with `model` field
- **THEN** adapter SHALL extract model ID for ClaudeController initialization

### Requirement: ClaudeController lifecycle management
The adapter SHALL manage ClaudeController instances with proper startup and cleanup.

#### Scenario: Controller startup
- **WHEN** adapter needs to send first request for a session
- **THEN** adapter SHALL create ClaudeController, start it, wait for init, then send message

#### Scenario: Controller reuse
- **WHEN** adapter receives request for existing session
- **THEN** adapter SHALL reuse existing ClaudeController and send message via `send()`

### Requirement: Subprocess lifecycle management
The adapter SHALL handle subprocess signals to prevent zombie and orphaned processes.

#### Scenario: SIGTERM received
- **WHEN** adapter process receives SIGTERM
- **THEN** adapter SHALL send SIGTERM to all ClaudeController subprocesses and wait for graceful shutdown (5s timeout), then exit

#### Scenario: SIGCHLD received
- **WHEN** a ClaudeController subprocess terminates unexpectedly
- **THEN** adapter SHALL detect via SIGCHLD, mark session as terminated, clean up resources, and return HTTP 500 to pending requests

#### Scenario: Zombie process prevention
- **WHEN** a ClaudeController subprocess exits
- **THEN** adapter SHALL reap zombie by calling wait() on the subprocess PID within SIGCHLD handler

#### Scenario: Orphaned subprocess cleanup
- **WHEN** adapter starts and finds existing claude-node processes from previous runs
- **THEN** adapter SHALL terminate orphaned processes before starting new sessions

#### Scenario: Graceful shutdown timeout
- **WHEN** adapter is shutting down and ClaudeController does not respond to SIGTERM within 5 seconds
- **THEN** adapter SHALL send SIGKILL to force termination

### Requirement: Response format conversion
The adapter SHALL convert ClaudeController result to OpenAI-compatible response format.

#### Scenario: Convert result to chat completion
- **WHEN** ClaudeController returns result via `on_message` with `type: "result"`
- **THEN** adapter SHALL extract `result_text` and format as OpenAI chat completion response

#### Scenario: Convert result with usage
- **WHEN** ClaudeController returns result via `on_message` with `type: "result"`
- **THEN** adapter SHALL include `usage` object with token counts from response metadata

### Requirement: Error handling
The adapter SHALL handle claude-node errors and convert to appropriate HTTP responses with unified error codes.

#### Scenario: ClaudeSendConflictError
- **WHEN** ClaudeController `send()` is called while another send is in-flight
- **THEN** adapter SHALL return HTTP 409 with error JSON matching API spec format:
```json
{
  "error": {
    "message": "Request conflict: another request is in-flight",
    "type": "conflict_error",
    "code": 409
  }
}
```

#### Scenario: Subprocess crash
- **WHEN** ClaudeController subprocess crashes during request
- **THEN** adapter SHALL return HTTP 500 with error JSON matching API spec format:
```json
{
  "error": {
    "message": "Subprocess failure",
    "type": "internal_error",
    "code": 500
  }
}
```

#### Scenario: Session not found
- **WHEN** adapter receives request for non-existent session
- **THEN** adapter SHALL return HTTP 404 with error JSON matching API spec format

#### Scenario: Rate limit exceeded
- **WHEN** ClaudeController reports rate limit exceeded
- **THEN** adapter SHALL return HTTP 429 with error JSON matching API spec format
