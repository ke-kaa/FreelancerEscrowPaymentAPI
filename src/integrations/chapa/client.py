"""
Chapa HTTP client.

Owns all `requests` calls to the Chapa API. No domain knowledge, no DTOs.
Failures surface as `requests.RequestException`; the adapter wraps them
as `ProviderError`.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

from common.resilience.circuit_breaker import circuit_breaker
from common.resilience.retry import retry

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.chapa.co/v1"
_RETRY_ON = (requests.ConnectionError, requests.Timeout)


class ChapaClient:
    def __init__(self) -> None:
        self.secret_key = settings.CHAPA_SECRET_KEY
        self.callback_url = settings.CHAPA_CALLBACK_URL
        self.return_url = settings.CHAPA_RETURN_URL
        self.base_url = _BASE_URL

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="chapa.initialize", on=_RETRY_ON)
    def initialize_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = requests.post(
            f"{self.base_url}/transaction/initialize",
            json=payload,
            headers=self._headers,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="chapa.verify", on=_RETRY_ON)
    def verify_transaction(self, tx_ref: str) -> dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/transaction/verify/{tx_ref}",
            headers=self._headers,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="chapa.refund", on=_RETRY_ON)
    def refund(self, tx_ref: str, form_data: str) -> dict[str, Any]:
        r = requests.post(
            f"{self.base_url}/refund/{tx_ref}",
            data=form_data,
            headers={
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="chapa.transfer", on=_RETRY_ON)
    def transfer(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = requests.post(
            f"{self.base_url}/transfers",
            json=payload,
            headers=self._headers,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="chapa.transfer.verify", on=_RETRY_ON)
    def verify_transfer(self, reference: str) -> dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/transfers/verify/{reference}",
            headers=self._headers,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    @retry(on=_RETRY_ON, max_attempts=3)
    @circuit_breaker(name="chapa.banks", on=_RETRY_ON)
    def list_banks(self) -> dict[str, Any]:
        r = requests.get(f"{self.base_url}/banks", headers=self._headers, timeout=10)
        r.raise_for_status()
        return r.json()
