"""
Async Background Worker
========================
Handles async processing of signals from an in-memory queue.
Implements retry logic with exponential back-off for persistence writes.

In production this queue would be replaced by a Kafka consumer.
"""

import asyncio
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

# In-memory bounded queue — absorbs bursts up to 50,000 signals
# without blocking the HTTP ingestion path (backpressure mechanism)
signal_queue: asyncio.Queue = asyncio.Queue(maxsize=50_000)

_worker_task = None


async def enqueue_signal(signal_data: dict) -> bool:
    """
    Non-blocking enqueue. Returns False if queue is full (backpressure applied).
    The caller should return a 429 or log a drop metric.
    """
    try:
        signal_queue.put_nowait(signal_data)
        return True
    except asyncio.QueueFull:
        logger.warning("[WORKER] Queue full — signal dropped (backpressure active)")
        return False


async def _retry_with_backoff(fn: Callable, *args, retries: int = 3, base_delay: float = 0.5) -> Any:
    """
    Retry a coroutine or callable up to `retries` times with exponential back-off.
    Used to wrap persistence writes so transient DB failures don't crash the worker.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            if asyncio.iscoroutinefunction(fn):
                return await fn(*args)
            return fn(*args)
        except Exception as exc:
            last_exc = exc
            delay = base_delay * (2 ** (attempt - 1))  # 0.5s, 1s, 2s
            logger.error(
                f"[WORKER] Attempt {attempt}/{retries} failed: {exc}. "
                f"Retrying in {delay:.1f}s…"
            )
            await asyncio.sleep(delay)
    logger.error(f"[WORKER] All {retries} retries exhausted: {last_exc}")
    raise last_exc


async def _process_queue(process_fn: Callable):
    """
    Main worker loop. Drains the queue and calls process_fn for each signal.
    process_fn is the debounce_service.process_signal function.
    """
    logger.info("[WORKER] Signal processing worker started")
    while True:
        try:
            signal = await signal_queue.get()
            try:
                await _retry_with_backoff(process_fn, signal)
            except Exception as exc:
                logger.error(f"[WORKER] Permanently failed to process signal: {exc}")
            finally:
                signal_queue.task_done()
        except asyncio.CancelledError:
            logger.info("[WORKER] Worker cancelled — shutting down")
            break
        except Exception as exc:
            logger.error(f"[WORKER] Unexpected error in worker loop: {exc}")


def start_worker(process_fn: Callable):
    """
    Launch the background worker as an asyncio Task.
    Call this from FastAPI's startup event.
    """
    global _worker_task
    loop = asyncio.get_event_loop()
    _worker_task = loop.create_task(_process_queue(process_fn))
    logger.info("[WORKER] Background worker task scheduled")


async def stop_worker():
    """
    Gracefully cancel the worker task on shutdown.
    Call this from FastAPI's shutdown event.
    """
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    logger.info("[WORKER] Worker stopped")


def queue_size() -> int:
    """Return current number of unprocessed signals in the queue."""
    return signal_queue.qsize()