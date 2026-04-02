#!/usr/bin/env python3
"""Main entry point for openclaw-claude-bridge."""
import sys
import signal
from config.settings import HOST, PORT


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down...")
    from claude_node_adapter.adapter import shutdown_all
    shutdown_all()
    sys.exit(0)


def main():
    """Run the bridge server."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    import uvicorn
    from openai_compatible_api.server import app

    print(f"Starting openclaw-claude-bridge on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
