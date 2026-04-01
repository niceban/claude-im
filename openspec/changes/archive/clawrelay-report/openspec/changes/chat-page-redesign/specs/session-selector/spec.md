# Session Selector

## ADDED Requirements

### Requirement: Session selector dropdown displays current session

The session selector SHALL display the currently selected session ID (truncated to 8 characters) in a dropdown button at the top of the Chat page. The dropdown SHALL display a list of recent sessions accessible to the current user.

#### Scenario: Display current session
- **WHEN** the Chat page loads
- **THEN** the selector button SHALL show "Session: abc123... ▼" where abc123 is the truncated current session ID

#### Scenario: Open dropdown
- **WHEN** the user clicks the session selector button
- **THEN** a dropdown list SHALL appear showing session ID, last active time, and a hover-edit icon for each session

#### Scenario: Hover reveals edit icon
- **WHEN** the user hovers over a session item in the dropdown
- **THEN** a pencil (✏️) icon SHALL appear on the right side of that item

### Requirement: Switching sessions changes displayed conversation

Selecting a different session from the dropdown SHALL update the conversation history in the middle panel and reset the tool status panel.

#### Scenario: Switch to different session
- **WHEN** the user clicks a different session in the dropdown
- **THEN** the middle panel SHALL load and display that session's conversation history
- **AND** the right panel SHALL reset and show the tool status for the newly selected session

### Requirement: Create new session from dropdown

The dropdown SHALL include a "Create new session" action at the top that creates a new session and navigates to it.

#### Scenario: Create new session
- **WHEN** the user clicks "Create new session" in the dropdown
- **THEN** the system SHALL create a new session via `POST /api/v1/chat/sessions`
- **AND** the UI SHALL navigate to the new session and display it

### Requirement: Admin can rename any session

Admin users SHALL be able to rename any session by clicking the edit icon and entering a new name.

#### Scenario: Admin renames session
- **WHEN** an admin user hovers over a session item and clicks the edit icon
- **THEN** an input field SHALL appear for inline editing
- **AND** on Enter or blur, the session name SHALL be saved via `PATCH /api/v1/admin/sessions/{id}`
- **AND** the dropdown SHALL update to show the new name
