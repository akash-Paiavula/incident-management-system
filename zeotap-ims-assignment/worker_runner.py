"""
Worker Runner
=============
Standalone entry point to run the async signal processing worker
independently of the FastAPI server (useful for scaling workers separately).

Usage:
  python worker_runner.py

In Docker Compose this can be added as a separate service:
  command: python worker_runner.py
"""

import asyncio
import logging
import signal
import sys

from app.services.worker import _process_queue, signal_queue
from app.services.debounce_service import process_signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("[RUNNER] Starting standalone signal worker...")

    loop = asyncio.get_running_loop()

    # Graceful shutdown on SIGINT / SIGTERM
    stop_event = asyncio.Event()

    def _shutdown(sig):
        logger.info(f"[RUNNER] Received {sig.name}, shutting down...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    worker_task = asyncio.create_task(_process_queue(process_signal))

    logger.info(f"[RUNNER] Worker running. Queue capacity: {signal_queue.maxsize}")
    await stop_event.wait()

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    logger.info("[RUNNER] Worker stopped cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)