"""
Thin Stripe SDK wrapper.

Owns ALL `stripe` SDK calls. No DTO translation, no domain exceptions —
the adapter layer handles those. Configures `stripe.api_key` at module
import from settings, NOT per-instance, to avoid surprise reassignment.
"""

from __future__ import annotations

import logging
from typing import Any

import stripe
from django.conf import settings

from common.resilience.circuit_breaker import circuit_breaker
from common.resilience.retry import retry

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

_RETRY_ON = (stripe.error.APIConnectionError, stripe.error.APIError, stripe.error.RateLimitError)


class StripeClient:
    """Thin wrappers around the Stripe Python SDK."""

    def __init__(self) -> None:
        self.currency = getattr(settings, "STRIPE_CURRENCY", "usd")
        self.country = getattr(settings, "STRIPE_COUNTRY", "US")
        self.webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="stripe.payment_intent.create", on=_RETRY_ON)
    def create_payment_intent(
        self,
        *,
        amount_cents: int,
        currency: str,
        receipt_email: str,
        description: str,
        metadata: dict[str, str],
    ) -> Any:
        return stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            receipt_email=receipt_email,
            description=description,
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
        )

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="stripe.payment_intent.retrieve", on=_RETRY_ON)
    def retrieve_payment_intent(self, intent_id: str) -> Any:
        return stripe.PaymentIntent.retrieve(intent_id)

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="stripe.refund.create", on=_RETRY_ON)
    def create_refund(self, **params: Any) -> Any:
        return stripe.Refund.create(**params)

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="stripe.transfer.create", on=_RETRY_ON)
    def create_transfer(self, **params: Any) -> Any:
        return stripe.Transfer.create(**params)

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="stripe.account_link.create", on=_RETRY_ON)
    def create_account_link(self, *, account_id: str, refresh_url: str, return_url: str) -> Any:
        return stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )

    def construct_webhook_event(self, payload: bytes, signature: str) -> Any:
        return stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
