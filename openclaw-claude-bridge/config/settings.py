"""Configuration settings for openclaw-claude-bridge."""
import os

# API Key authentication
_API_KEY = os.getenv("BRIDGE_API_KEY", "change-me-in-production")
# Validate API_KEY is set to a production value
if not _API_KEY or _API_KEY == "change-me-in-production":
    raise ValueError(
        "BRIDGE_API_KEY must be set to a secure value. "
        "Hint: export BRIDGE_API_KEY='your-secret-key'"
    )
API_KEY = _API_KEY

# Server settings
HOST = os.getenv("BRIDGE_HOST", "0.0.0.0")
PORT = int(os.getenv("BRIDGE_PORT", "18792"))

# Session settings
MAX_POOL_SIZE = int(os.getenv("MAX_POOL_SIZE", "50"))
IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "1800"))  # 30 minutes

# claude-node settings
CLAUDE_NODE_PATH = os.getenv("CLAUDE_NODE_PATH", "/private/tmp/claude-node")
CLAUDE_NODE_VERSION = "1.0.0"  # Pinned version
CLAUDE_NODE_TIMEOUT = int(os.getenv("CLAUDE_NODE_TIMEOUT", "120"))  # 2 minutes

# Request settings
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))

# Tmux settings (for interactive prompts - 1% use case)
TMUX_ENABLED = os.getenv("TMUX_ENABLED", "false").lower() == "true"
TMUX_MODE = os.getenv("TMUX_MODE", "off")  # "off", "passive", "active"
MAX_TMUX_SESSIONS = int(os.getenv("MAX_TMUX_SESSIONS", "10"))
TMUX_SESSION_TIMEOUT = int(os.getenv("TMUX_SESSION_TIMEOUT", "300"))  # 5 minutes
