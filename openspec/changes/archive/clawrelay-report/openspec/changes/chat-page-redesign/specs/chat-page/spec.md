# Chat Page

## ADDED Requirements

### Requirement: Chat page layout is three-column

The Chat page SHALL display a three-column layout: left sidebar (navigation), center conversation area, right tool status panel (collapsible).

#### Scenario: Three-column layout
- **WHEN** the Chat page loads
- **THEN** the layout SHALL show: left sidebar | center conversation | right tool panel (if not collapsed)

#### Scenario: Right panel collapsible
- **WHEN** the right panel is collapsed
- **THEN** the layout SHALL show: left sidebar | center conversation (full width)

### Requirement: Conversation area displays message history

The center panel SHALL display the conversation history for the selected session, with user messages and assistant responses in a chat bubble format.

#### Scenario: Load conversation history
- **WHEN** a session is selected
- **THEN** the center panel SHALL load and display messages from `GET /api/v1/chat/sessions/{id}/history`
- **AND** messages SHALL be displayed with user messages on one side and assistant messages on the other

#### Scenario: Send new message
- **WHEN** the user types a message and clicks Send (or presses Enter)
- **THEN** the user message SHALL be immediately displayed in the conversation
- **AND** a "processing" indicator SHALL be shown for the incoming assistant response
- **AND** the message SHALL be sent to `POST /api/v1/chat/sessions/{id}/messages`

#### Scenario: Empty state with no sessions
- **WHEN** the user has no sessions
- **THEN** the center panel SHALL display an empty state with a prompt to create a new session
- **AND** the prompt SHALL include a "Create new session" button

### Requirement: Input area at bottom of conversation

The bottom of the center panel SHALL contain a message input area with a send button.

#### Scenario: Message input
- **WHEN** the user types in the input field
- **THEN** the text SHALL be displayed in the input
- **AND** pressing Enter (without Shift) OR clicking Send SHALL submit the message

#### Scenario: Send button disabled when empty
- **WHEN** the input field is empty
- **THEN** the Send button SHALL be disabled

### Requirement: Real-time updates via WebSocket

The Chat page SHALL maintain a WebSocket connection to receive real-time updates for the current session.

#### Scenario: Delta events accumulate
- **WHEN** a `delta` WebSocket event is received
- **THEN** the text SHALL be appended to the last assistant message in the conversation

#### Scenario: Done event finalizes message
- **WHEN** a `done` WebSocket event is received
- **THEN** the "processing" indicator SHALL be removed
- **AND** the conversation history SHALL be refetched to ensure consistency

#### Scenario: Error event shows notification
- **WHEN** an `error` WebSocket event is received
- **THEN** an error notification SHALL be displayed
- **AND** the "processing" indicator SHALL be removed
