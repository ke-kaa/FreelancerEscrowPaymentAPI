"""
@atomic_with_lock — wrap a service method in `transaction.atomic()` plus
`select_for_update()` on a target row.

This is the primitive Phase 5 applies to every state-mutating escrow /
payment service. Forces locking discipline to be mechanical rather than
remembered.

Usage:
    @atomic_with_lock(model=EscrowTransaction, lookup="escrow_id", inject_as="escrow")
    def release_funds(self, *, escrow_id, ...):
        # `escrow` is row-locked and injected here

Caveats:
- select_for_update() is a NO-OP on SQLite. Tests that rely on locking
  MUST run against Postgres (config.settings.testing uses DATABASE_URL).
- Keep external network calls (provider HTTP) OUTSIDE the locked block.
  Pre-debit balance inside the lock, then call the provider after commit,
  with a stored idempotency key for retry safety.

Refs: MIGRATION_PLAN.md Phase 5; ARCHITECTURE_AUDIT.md §7
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from django.db import transaction

F = TypeVar("F", bound=Callable[..., Any])


def atomic_with_lock(
    *,
    model: type,
    lookup: str,
    inject_as: str | None = None,
    using: str | None = None,
) -> Callable[[F], F]:
    """
    Args:
        model:     Django model class whose row will be locked.
        lookup:    Kwarg name on the call holding the row's pk; popped before forwarding.
        inject_as: Kwarg name to inject the locked instance under. Defaults
                   to lowercased model name.
        using:     DB alias if non-default.
    """
    inject_name = inject_as or model.__name__.lower()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            if lookup not in kwargs:
                raise TypeError(
                    f"@atomic_with_lock: {func.__qualname__} called without required kwarg {lookup!r}"
                )
            pk = kwargs.pop(lookup)
            with transaction.atomic(using=using):
                qs = model.objects.select_for_update()
                if using:
                    qs = qs.using(using)
                instance = qs.get(pk=pk)
                kwargs[inject_name] = instance
                return func(self, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
