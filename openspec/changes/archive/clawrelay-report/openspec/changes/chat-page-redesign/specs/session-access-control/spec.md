# Session Access Control

## ADDED Requirements

### Requirement: Regular users can only see their own sessions

Non-admin users SHALL only see sessions where `owner_id` matches their user ID in the session selector dropdown.

#### Scenario: Regular user sees only their sessions
- **WHEN** a non-admin user opens the session selector
- **THEN** the dropdown SHALL only display sessions created by that user

#### Scenario: Regular user cannot access other user's session
- **WHEN** a non-admin user tries to navigate to another user's session via URL
- **THEN** the system SHALL return a 403 Forbidden or redirect to an error page

### Requirement: Admin users can see and manage all sessions

Admin users SHALL see all sessions in the session selector and SHALL be able to rename any session.

#### Scenario: Admin sees all sessions
- **WHEN** an admin user opens the session selector
- **THEN** the dropdown SHALL display all sessions in the system

#### Scenario: Admin can rename any session
- **WHEN** an admin user clicks the edit icon on any session
- **THEN** an input field SHALL appear for inline editing
- **AND** on save, the session name SHALL be updated via `PATCH /api/v1/admin/sessions/{id}`

### Requirement: Session ownership is tracked

Each session SHALL have an `owner_id` field that identifies the user who created it.

#### Scenario: New session records owner
- **WHEN** a user creates a new session
- **THEN** the session SHALL be associated with that user's ID as the owner
