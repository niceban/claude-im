# session-mapping

## ADDED Requirements

### Requirement: SessionBackend Abstract Interface
The session-mapping module SHALL provide a `SessionBackend` abstract interface for lifecycle operations.

#### Interface: SessionBackend
```
SessionBackend:
  - create_session(session_id: str) -> None
  - destroy_session(session_id: str) -> None
  - is_session_alive(session_id: str) -> bool
```

#### Scenario: Backend abstraction used by adapter
- **WHEN** claude-node-adapter needs to manage session lifecycle
- **THEN** adapter SHALL use SessionBackend interface to create/destroy sessions (not direct subprocess management)

#### Scenario: Mock backend for testing
- **WHEN** testing session-mapping without real claude-node
- **THEN** tests SHALL use mock SessionBackend implementing SessionBackend interface

### Requirement: Conversation ID to Session ID mapping
The system SHALL maintain a mapping from OpenAI `conversation_id` (or generated ID) to claude-node `session_id`.

#### Scenario: Create new session mapping
- **WHEN** first request is received with no `conversation_id`
- **THEN** system SHALL generate a new session_id, store mapping, call `SessionBackend.create_session()`, and pass session_id to ClaudeController

#### Scenario: Resume existing session
- **WHEN** request includes `conversation_id` that exists in mapping
- **THEN** system SHALL retrieve corresponding session_id, verify via `SessionBackend.is_session_alive()`, and pass to ClaudeController for resume

### Requirement: LRU session eviction
The system SHALL evict least recently used sessions when pool size exceeds limit.

#### Scenario: Pool full, evict LRU
- **WHEN** session count equals MAX_POOL_SIZE and new session is needed
- **THEN** system SHALL evict the least recently used session, call `SessionBackend.destroy_session()`, and remove from mapping

#### Scenario: Session access updates LRU
- **WHEN** request accesses an existing session
- **THEN** system SHALL update its last_used timestamp

### Requirement: Session cleanup on timeout
The system SHALL clean up sessions that have been idle beyond timeout threshold.

#### Scenario: Idle session timeout
- **WHEN** a session has been idle for longer than IDLE_TIMEOUT seconds
- **THEN** system SHALL call `SessionBackend.destroy_session()` and remove from mapping
