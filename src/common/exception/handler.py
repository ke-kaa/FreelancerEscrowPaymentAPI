"""
Custom DRF exception handler.

Wires into settings via `REST_FRAMEWORK["EXCEPTION_HANDLER"]`. All errors
leave the API in a single envelope: `{code, message, details}`.

Refs: MIGRATION_PLAN.md Phase 3; ARCHITECTURE_AUDIT.md §6
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

from common.exception.domain import DomainError

logger = logging.getLogger(__name__)


def _envelope(*, code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details or {}}


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, DomainError):
        return Response(exc.to_dict(), status=exc.http_status)

    if isinstance(exc, Http404):
        return Response(_envelope(code="not_found", message="Resource not found"), status=404)

    if isinstance(exc, PermissionDenied):
        return Response(_envelope(code="permission_denied", message=str(exc) or "Permission denied"), status=403)

    response = drf_default_handler(exc, context)
    if response is not None:
        code = getattr(exc, "default_code", None) or "error"
        message = _flatten_drf_message(response.data)
        response.data = _envelope(code=code, message=message, details=response.data)
        return response

    logger.exception("Unhandled exception in API")
    return Response(
        _envelope(code="internal_error", message="An unexpected error occurred."),
        status=500,
    )


def _flatten_drf_message(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for v in payload.values():
            msg = _flatten_drf_message(v)
            if msg:
                return msg
    if isinstance(payload, list) and payload:
        return _flatten_drf_message(payload[0])
    return "Request invalid."
