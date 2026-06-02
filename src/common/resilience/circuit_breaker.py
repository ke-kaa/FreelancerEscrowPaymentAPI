"""
Minimal in-memory circuit breaker.

After `failure_threshold` consecutive failures, opens for `reset_timeout`
seconds; calls during the open window raise `CircuitOpen` immediately.

Process-local — a multi-worker deployment has one breaker per worker.
Replace with Redis-backed implementation if the failure-rate signal needs
to be shared.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CircuitOpen(Exception):
    """Raised when calls are short-circuited by an open breaker."""


class _State:
    __slots__ = ("failures", "opened_at", "lock")

    def __init__(self) -> None:
        self.failures = 0
        self.opened_at: float | None = None
        self.lock = threading.Lock()


_breakers: dict[str, _State] = {}


def circuit_breaker(
    *,
    name: str,
    failure_threshold: int = 5,
    reset_timeout: float = 30.0,
    on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    state = _breakers.setdefault(name, _State())

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with state.lock:
                if state.opened_at is not None:
                    if time.monotonic() - state.opened_at < reset_timeout:
                        raise CircuitOpen(f"circuit '{name}' is open")
                    # half-open: try one
                    state.opened_at = None
                    state.failures = 0

            try:
                result = func(*args, **kwargs)
            except on as exc:
                with state.lock:
                    state.failures += 1
                    if state.failures >= failure_threshold:
                        state.opened_at = time.monotonic()
                        logger.warning(
                            "circuit '%s' opened after %s failures: %s",
                            name, state.failures, exc,
                        )
                raise

            with state.lock:
                state.failures = 0
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
