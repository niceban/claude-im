"""Configuration module for clawrelay-bridge"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Bridge server configuration."""

    # Server settings
    host: str = "127.0.0.1"
    port: int = 18792

    # claude-node settings
    claude_model: str = "claude-sonnet-4-6"
    claude_working_dir: str = ""
    claude_env_vars: dict = field(default_factory=dict)

    # Health monitor settings
    health_check_interval: int = 30  # seconds

    # Fallback settings
    fallback_failure_threshold: int = 3  # consecutive failures before fallback
    fallback_success_threshold: int = 3  # consecutive successes before recovery

    # Database path
    db_path: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Server settings
        config.host = os.getenv("BRIDGE_HOST", config.host)
        config.port = int(os.getenv("BRIDGE_PORT", config.port))

        # claude-node settings
        config.claude_model = os.getenv("CLAUDE_MODEL", config.claude_model)
        config.claude_working_dir = os.getenv("CLAUDE_WORKING_DIR", config.claude_working_dir)

        # claude-node env vars
        for key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_API_KEY"):
            if key in os.environ:
                config.claude_env_vars[key] = os.environ[key]

        # Override from CLAUDE_* vars
        if api_key := os.getenv("CLAUDE_API_KEY"):
            config.claude_env_vars["ANTHROPIC_AUTH_TOKEN"] = api_key

        # Health monitor settings
        config.health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", config.health_check_interval))

        # Fallback settings
        config.fallback_failure_threshold = int(os.getenv("FALLBACK_FAILURE_THRESHOLD", config.fallback_failure_threshold))
        config.fallback_success_threshold = int(os.getenv("FALLBACK_SUCCESS_THRESHOLD", config.fallback_success_threshold))

        # Database path
        config.db_path = os.getenv("BRIDGE_DB_PATH", str(Path.home() / ".openclaw-claude-bridge" / "bridge.db"))

        return config
