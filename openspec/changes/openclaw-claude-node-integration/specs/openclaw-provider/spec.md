## ADDED Requirements

### Requirement: OpenClaw Provider Configuration
OpenClaw SHALL use the custom Provider plugin mechanism to configure claude-node Bridge as an AI backend via `models.providers` in `openclaw.json`.

### Requirement: Provider API Type Support
The Provider SHALL support `openai-completions` API type for compatibility with OpenClaw's Provider plugin system.

### Requirement: Model Declaration
The Provider SHALL declare available models including `claude-sonnet-4-6` with proper context window (200000) and max tokens (8192) configuration.

### Requirement: Environment Variable Substitution
The Provider SHALL support environment variable substitution in configuration values using `${VAR_NAME}` syntax.

---

#### Scenario: Provider loads successfully
- **WHEN** OpenClaw starts with claude-node Provider configured
- **THEN** OpenClaw SHALL connect to Bridge Server at `http://127.0.0.1:18792`
- **AND** SHALL list available models via `GET /v1/models`

#### Scenario: Chat completions request
- **WHEN** User sends a message that triggers AI inference
- **THEN** OpenClaw SHALL forward the request to `POST /v1/chat/completions`
- **AND** SHALL return the response in OpenAI-compatible format

#### Scenario: Provider configuration merge
- **WHEN** `models.mode` is set to `"merge"`
- **THEN** claude-node Provider SHALL be added to existing providers
- **AND** SHALL NOT replace bundled providers
