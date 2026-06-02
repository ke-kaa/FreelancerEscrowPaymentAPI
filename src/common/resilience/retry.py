"""
Retry decorator for external HTTP calls.

Wraps a callable in bounded retries with exponential backoff and jitter.
Only retries on the configured exception types — never blanket Exception.
"""

from __future__ import annotations

import functools
import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def retry(
    *,
    on: tuple[type[BaseException], ...],
    max_attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
    jitter: float = 0.1,
) -> Callable[[F], F]:
    """
    Args:
        on:           Exception types to retry on (everything else propagates).
        max_attempts: Total attempts including the first. Must be >= 1.
        base_delay:   Initial backoff seconds.
        max_delay:    Ceiling for backoff seconds.
        jitter:       Random jitter [0, jitter] added to each sleep.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                attempt += 1
                try:
                    return func(*args, **kwargs)
                except on as exc:
                    if attempt >= max_attempts:
                        logger.warning(
                            "retry exhausted for %s after %s attempts: %s",
                            func.__qualname__, attempt, exc,
                        )
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay += random.uniform(0, jitter)
                    logger.info(
                        "retrying %s (attempt %s/%s) in %.2fs after %s",
                        func.__qualname__, attempt, max_attempts, delay, type(exc).__name__,
                    )
                    time.sleep(delay)

        return wrapper  # type: ignore[return-value]

    return decorator
