"""CLI entry point for clawrelay-bridge"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from clawrelay_bridge.config import Config
from clawrelay_bridge.server import BridgeServer


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )


async def main():
    """Main entry point."""
    setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    logger = logging.getLogger(__name__)

    config = Config.from_env()
    logger.info(f"Starting clawrelay-bridge on {config.host}:{config.port}")

    server = BridgeServer(config)

    # Graceful shutdown
    loop = asyncio.get_running_loop()

    def shutdown_handler():
        logger.info("Shutdown signal received")
        server.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_handler)

    await server.start()
    logger.info("clawrelay-bridge stopped")


if __name__ == "__main__":
    asyncio.run(main())
