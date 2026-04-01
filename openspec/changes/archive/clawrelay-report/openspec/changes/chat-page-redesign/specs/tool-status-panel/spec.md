# Tool Status Panel

## ADDED Requirements

### Requirement: Tool status panel displays real-time tool usage

The tool status panel SHALL display a real-time timeline of tools called by Claude during the current message processing. The panel SHALL be located on the right side of the Chat page and SHALL be collapsible.

#### Scenario: Panel visible by default
- **WHEN** the Chat page loads with a selected session
- **THEN** the tool status panel SHALL be visible on the right side

#### Scenario: ToolUseStart event adds entry
- **WHEN** `stream_chat()` emits a `ToolUseStart(name="X")` event
- **THEN** the panel SHALL immediately display a new entry: "▶ {ToolName}" with an expand arrow
- **AND** the entry SHALL show as "running" (spinner or loading indicator)

#### Scenario: Tool execution completes
- **WHEN** the `done` WebSocket event is received for a message
- **THEN** all tool entries for that message SHALL show "✓" (checkmark) indicating completion
- **AND** the running indicator SHALL be replaced with success state

#### Scenario: Panel can be collapsed
- **WHEN** the user clicks the collapse button (−) in the panel header
- **THEN** the panel SHALL collapse to hide its content, showing only the collapse/expand toggle
- **AND** clicking the expand button (+) SHALL restore the panel

### Requirement: Tool entries are grouped per message

The tool entries SHALL be grouped per user message, showing which tools were called in response to which message.

#### Scenario: New message starts new group
- **WHEN** a new user message is sent
- **THEN** a visual divider or label SHALL indicate a new group of tool calls
- **AND** previous tool entries SHALL remain visible (scrollable if needed)

### Requirement: Panel shows only tool names (no parameters or output)

The panel SHALL display only the tool names and execution status, not the tool parameters or command output.

#### Scenario: Tool entry format
- **WHEN** a tool is called (e.g., Bash)
- **THEN** the entry SHALL show: "▶ Bash" with status indicator
- **AND** the entry SHALL NOT show command arguments, stdout, or stderr
