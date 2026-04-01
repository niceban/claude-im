## ADDED Requirements

### Requirement: Session Mapping Table
The system SHALL maintain a SQLite table `session_mapping` that stores 1:1 mappings between OpenClaw sessions and claude-node sessions.

### Requirement: Table Schema
The session_mapping table SHALL have the following schema:
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `openclaw_session_id`: TEXT UNIQUE NOT NULL
- `claude_session_id`: TEXT UNIQUE NOT NULL
- `platform`: TEXT
- `user_id`: TEXT
- `created_at`: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `last_active`: TIMESTAMP
- `status`: TEXT DEFAULT 'active' (active|paused|archived)

### Requirement: Create Session Mapping
When a new OpenClaw session is created, the system SHALL create a corresponding claude-node session and store the mapping.

#### Scenario: New session mapping
- **WHEN** OpenClaw creates a new session
- **THEN** Bridge SHALL create a new claude-node session
- **AND** SHALL insert mapping into session_mapping table

### Requirement: Lookup Session Mapping
The system SHALL be able to look up claude_session_id by openclaw_session_id and vice versa.

#### Scenario: Lookup by OpenClaw session ID
- **WHEN** Bridge receives message with openclaw_session_id
- **THEN** Bridge SHALL query session_mapping for corresponding claude_session_id
- **AND** SHALL route message to that claude-node session

### Requirement: Update Last Active
The system SHALL update `last_active` timestamp on each message.

#### Scenario: Update last active
- **WHEN** Message is sent through a session
- **THEN** Bridge SHALL update session_mapping SET last_active = CURRENT_TIMESTAMP

### Requirement: Session Cleanup
The system SHALL mark sessions as 'archived' when closed.

#### Scenario: Archive closed session
- **WHEN** OpenClaw closes a session
- **THEN** Bridge SHALL update session_mapping SET status = 'archived'
