# openai-compatible-api

## ADDED Requirements

### Requirement: API Key Authentication
The system SHALL validate API Key on all endpoints using `X-API-Key` header.

#### Scenario: Missing API Key
- **WHEN** client sends request without `X-API-Key` header
- **THEN** system returns HTTP 401 with error JSON:
```json
{
  "error": {
    "message": "Missing API Key",
    "type": "authentication_error",
    "code": 401
  }
}
```

#### Scenario: Invalid API Key
- **WHEN** client sends request with invalid `X-API-Key` header
- **THEN** system returns HTTP 401 with error JSON:
```json
{
  "error": {
    "message": "Invalid API Key",
    "type": "authentication_error",
    "code": 401
  }
}
```

### Requirement: POST /v1/chat/completions endpoint
The system SHALL provide a `POST /v1/chat/completions` endpoint compatible with OpenAI API specification.

#### Scenario: Successful non-streaming request
- **WHEN** client sends POST to `/v1/chat/completions` with valid API Key, JSON body containing `model`, `messages`, and `stream: false`
- **THEN** system returns JSON response with `id`, `object`, `created`, `model`, `choices` array containing message and `finish_reason`, and `usage` object

#### Scenario: Invalid request body
- **WHEN** client sends POST to `/v1/chat/completions` with missing required field `messages`
- **THEN** system returns HTTP 400 with error JSON:
```json
{
  "error": {
    "message": "Missing required field: messages",
    "type": "invalid_request_error",
    "code": 400
  }
}
```

#### Scenario: Model not found
- **WHEN** client sends POST to `/v1/chat/completions` with unknown model ID
- **THEN** system returns HTTP 400 with error JSON:
```json
{
  "error": {
    "message": "Model not found: <model_id>",
    "type": "invalid_request_error",
    "code": 400
  }
}
```

#### Scenario: Rate limit exceeded
- **WHEN** client sends POST to `/v1/chat/completions` and rate limit is exceeded
- **THEN** system returns HTTP 429 with error JSON:
```json
{
  "error": {
    "message": "Rate limit exceeded",
    "type": "rate_limit_error",
    "code": 429
  }
}
```

#### Scenario: Internal server error
- **WHEN** client sends POST to `/v1/chat/completions` and internal error occurs
- **THEN** system returns HTTP 500 with error JSON:
```json
{
  "error": {
    "message": "Internal server error",
    "type": "internal_error",
    "code": 500
  }
}
```

### Requirement: GET /health endpoint
The system SHALL provide a `GET /health` endpoint for health checks.

#### Scenario: Healthy service
- **WHEN** client sends GET to `/health`
- **THEN** system returns HTTP 200 with JSON `{"status": "healthy", "timestamp": <unix_timestamp>, "version": "<dynamic_version>"}` where version is read from package metadata

### Requirement: GET /v1/models endpoint
The system SHALL provide a `GET /v1/models` endpoint listing available models.

#### Scenario: List models
- **WHEN** client sends GET to `/v1/models` with valid API Key
- **THEN** system returns JSON with `object: "list"` and `data` array containing model objects with `id`, `object`, `created`, `name`, `context_window`

### Requirement: Request timeout handling
The system SHALL handle request timeouts gracefully.

#### Scenario: Request timeout
- **WHEN** client sends POST to `/v1/chat/completions` and claude-node does not respond within timeout
- **THEN** system returns HTTP 504 with error JSON:
```json
{
  "error": {
    "message": "Request timeout",
    "type": "timeout_error",
    "code": 504
  }
}
```

### Requirement: Usage field in response
The system SHALL include `usage` field in chat completion responses.

#### Scenario: Usage field present
- **WHEN** system returns successful chat completion response
- **THEN** response SHALL include `usage` object with `prompt_tokens`, `completion_tokens`, and `total_tokens`
