## ADDED Requirements

### Requirement: Non-blocking Controller Start
`ClaudeController.start(wait_init_timeout=0)` SHALL be called so the HTTP handler is not blocked by the subprocess cold-start.

### Requirement: Background Init Thread
After non-blocking start, a daemon `threading.Thread` SHALL be spawned to wait for init completion (up to 30 seconds). If init times out, the thread SHALL log a warning and exit.

### Requirement: Per-Session Send Thread
Each `/chat` request SHALL be handled by a separate `threading.Thread` that executes `controller.send()` in a thread pool, preventing blocking of the HTTP event loop.

### Requirement: Init-Complete Wait in Handler
If a newly started controller's init thread has not yet completed, the HTTP handler for that session SHALL wait up to 10 seconds for init to complete before returning an error.

### Requirement: Send Timeout
Each `controller.send()` call SHALL be subject to the configured `timeout` (default 300 seconds). If timeout is exceeded, the request SHALL return a PROCESS_ERROR response.

### Requirement: Signal Handling
The daemon SHALL register `SIGTERM` and `SIGINT` handlers that set `_shutdown_requested = True` and stop all pooled controllers before exiting.

#### Scenario: Non-blocking start
- **WHEN** a new controller is created for a session
- **THEN** `start(wait_init_timeout=0)` returns immediately and the HTTP handler is not blocked

#### Scenario: Init completes in background
- **WHEN** a new controller is started non-blocking
- **THEN** a daemon thread waits up to 30s for init to complete and logs success or timeout

#### Scenario: HTTP handler waits for init
- **WHEN** an HTTP request arrives for a session whose controller init is not yet complete
- **THEN** the handler waits up to 10s for init, returning error if timeout expires

#### Scenario: Graceful shutdown on SIGTERM
- **WHEN** SIGTERM is received
- **THEN** all pooled controllers are stopped, and the daemon exits with code 0

#### Scenario: Send times out
- **WHEN** `controller.send()` exceeds the configured timeout
- **THEN** a PROCESS_ERROR response is returned with error_code 103
