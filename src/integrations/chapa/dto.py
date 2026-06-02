"""Chapa-specific response shapes (kept thin)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChapaTransaction:
    tx_ref: str
    status: str
    raw: dict[str, Any]
