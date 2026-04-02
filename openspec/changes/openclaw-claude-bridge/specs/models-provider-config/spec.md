# models-provider-config

## ADDED Requirements

### Requirement: OpenClaw models.providers configuration
The system SHALL provide correct `models.providers` configuration for OpenClaw Gateway.

#### Scenario: Provider configuration
- **WHEN** OpenClaw Gateway is configured with `models.providers.claude-bridge`
- **THEN** Gateway SHALL send HTTP requests to bridge baseUrl for chat completions

### Requirement: baseUrl configuration
The configuration SHALL include correct `baseUrl` pointing to bridge service.

#### Scenario: Correct baseUrl format
- **WHEN** bridge runs on port 18792
- **THEN** baseUrl SHALL be `http://127.0.0.1:18792`

### Requirement: API type configuration
The configuration SHALL specify `api: "openai-completions"` for OpenAI-compatible interface.

#### Scenario: OpenAI completions API type
- **WHEN** OpenClaw Gateway processes requests for `claude-bridge` provider
- **THEN** Gateway SHALL use OpenAI completions API format

### Requirement: Model list configuration
The configuration SHALL include available models with context window settings.

#### Scenario: Model context window
- **WHEN** model supports 200k context
- **THEN** configuration SHALL specify `contextWindow: 200000`
