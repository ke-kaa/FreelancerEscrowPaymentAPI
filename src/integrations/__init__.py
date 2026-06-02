"""
Payment gateway registry.

Resolves provider name → `PaymentGateway` instance using
`settings.PAYMENT_GATEWAYS = {name: "dotted.path.to.adapter.Class"}`.
"""

from __future__ import annotations

from importlib import import_module

from django.conf import settings

from common.patterns.ports import PaymentGateway


def get_gateway(name: str) -> PaymentGateway:
    """
    Args:
        name: Provider name, e.g. "stripe" or "chapa".

    Raises:
        ValueError: name not in `PAYMENT_GATEWAYS` setting.
        ImportError: dotted path invalid.
    """
    mapping = getattr(settings, "PAYMENT_GATEWAYS", {})
    if name not in mapping:
        raise ValueError(f"Unknown payment gateway: {name!r}")
    dotted = mapping[name]
    module_path, class_name = dotted.rsplit(".", 1)
    cls = getattr(import_module(module_path), class_name)
    return cls()


__all__ = ["get_gateway", "PaymentGateway"]
