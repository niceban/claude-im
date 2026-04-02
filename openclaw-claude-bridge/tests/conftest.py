"""Pytest configuration - set up environment before tests."""
import os
import sys

# Ensure the package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set API key before importing server modules
os.environ["BRIDGE_API_KEY"] = "test-key"
os.environ["CLAUDE_NODE_PATH"] = "/private/tmp/claude-node"
