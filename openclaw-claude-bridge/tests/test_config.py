"""Tests for config module."""
import pytest
import json

import sys
sys.path.insert(0, 'openclaw-claude-bridge')

from config.generator import (
    generate_provider_config,
    generate_openclaw_json_patch,
)
from config.settings import API_KEY


class TestConfigGenerator:
    """Tests 4.1.x: Config generation correctness."""

    def test_generate_provider_config_structure(self):
        """Test 4.1.1: config generates correct structure."""
        config = generate_provider_config()

        # Verify top-level structure
        assert "claude-bridge" in config

        provider = config["claude-bridge"]
        assert provider["provider"] == "claude-bridge"
        assert provider["baseUrl"] == "http://127.0.0.1:18792"
        assert provider["api"] == "openai-completions"

        # Verify models structure
        assert "models" in provider
        models = provider["models"]
        assert "defaults" in models
        assert "items" in models

        # Verify defaults
        assert len(models["defaults"]) > 0
        assert models["defaults"][0]["model"] == "claude-sonnet-4-6"

        # Verify items
        assert len(models["items"]) > 0
        for item in models["items"]:
            assert "id" in item
            assert "contextWindow" in item

    def test_generate_provider_config_custom_host_port(self):
        """Test config respects custom host and port."""
        config = generate_provider_config(
            bridge_host="0.0.0.0",
            bridge_port=9000,
            provider_name="custom-provider"
        )

        provider = config["custom-provider"]
        assert provider["baseUrl"] == "http://0.0.0.0:9000"

    def test_generate_openclaw_json_patch(self):
        """Test patch generation returns valid fragment."""
        patch = generate_openclaw_json_patch()

        assert "claude-bridge" in patch
        # Should be ready to merge into openclaw.json models.providers

    def test_api_key_defined_in_settings(self):
        """Test 4.1.2: API_KEY is defined in settings."""
        assert API_KEY is not None
        assert len(API_KEY) > 0
        # Default should be change-me-in-production
        assert API_KEY != ""


class TestConfigModels:
    """Tests for model configuration."""

    def test_default_models_include_all_claude_models(self):
        """Test all expected Claude models are in config."""
        config = generate_provider_config()

        provider = config["claude-bridge"]
        items = provider["models"]["items"]

        model_ids = [item["id"] for item in items]

        assert "claude-sonnet-4-6" in model_ids
        assert "claude-opus-4-6" in model_ids
        assert "claude-haiku-4-5" in model_ids

    def test_context_window_defaults(self):
        """Test context window is set correctly."""
        config = generate_provider_config()

        provider = config["claude-bridge"]
        items = provider["models"]["items"]

        for item in items:
            assert item["contextWindow"] == 200000
