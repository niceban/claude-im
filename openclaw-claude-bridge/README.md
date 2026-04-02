# openclaw-claude-bridge

OpenAI-compatible API bridge between OpenClaw Gateway and claude-node.

## Architecture

```
Feishu → OpenClaw Gateway → models.providers → openclaw-claude-bridge → claude-node → Claude CLI
```

## Components

- `openai_compatible_api/` - Starlette HTTP server with OpenAI-compatible endpoints
- `claude_node_adapter/` - Protocol conversion and subprocess lifecycle management
- `session_mapping/` - Conversation ID to session ID mapping with LRU eviction
- `config/` - Configuration settings and OpenClaw config generator

## Setup

```bash
cd openclaw-claude-bridge
pip install -e .
```

## Configuration

Set environment variables:
- `BRIDGE_API_KEY` - API key for authentication (required)
- `BRIDGE_HOST` - Host to bind (default: 0.0.0.0)
- `BRIDGE_PORT` - Port to listen (default: 18792)
- `CLAUDE_NODE_PATH` - Path to claude-node (default: /private/tmp/claude-node)

## Running

```bash
# Development
python main.py

# Production (with uvicorn)
uvicorn openai_compatible_api.server:app --host 0.0.0.0 --port 18792
```

## API Endpoints

- `POST /v1/chat/completions` - Chat completion (requires X-API-Key header)
- `GET /health` - Health check
- `GET /v1/models` - List available models

## Testing

```bash
pytest tests/
```

## OpenClaw Configuration

Generate configuration:
```bash
python -m config.generator
```

Then add to `~/.openclaw/openclaw.json`:
```json
{
  "models": {
    "providers": {
      "claude-bridge": {
        "provider": "claude-bridge",
        "baseUrl": "http://127.0.0.1:18792",
        "api": "openai-completions",
        "models": {
          "defaults": [{"model": "claude-sonnet-4-6"}],
          "items": [
            {"id": "claude-sonnet-4-6", "contextWindow": 200000}
          ]
        }
      }
    }
  }
}
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v
```
