"""
Receivers that append TransactionLog entries on escrow / payment / dispute
status changes.

Light wiring — handlers detect status-field changes via post_save and
compare with the in-DB pre-state captured by pre_save.
"""

from __future__ import annotations

import logging
from threading import local

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .services import record_event

logger = logging.getLogger(__name__)

# Thread-local cache of pre-save snapshots keyed by (model_name, pk).
_cache = local()


def _snapshot(instance) -> dict:
    return {
        "status": getattr(instance, "status", None),
        "is_locked": getattr(instance, "is_locked", None),
        "current_balance": str(getattr(instance, "current_balance", "")) or None,
    }


def _key(instance) -> tuple[str, int | None]:
    return (instance.__class__.__name__, getattr(instance, "pk", None))


def _register(model_path: str, action_prefix: str):
    from django.apps import apps as django_apps

    app_label, model_name = model_path.split(".")
    model = django_apps.get_model(app_label, model_name)

    @receiver(pre_save, sender=model, weak=False)
    def _pre(sender, instance, **kwargs):
        if instance.pk is None:
            return
        try:
            prior = sender.objects.only("status", *(["is_locked"] if hasattr(instance, "is_locked") else []), *(["current_balance"] if hasattr(instance, "current_balance") else [])).get(pk=instance.pk)
        except sender.DoesNotExist:
            return
        if not hasattr(_cache, "snapshots"):
            _cache.snapshots = {}
        _cache.snapshots[_key(instance)] = _snapshot(prior)

    @receiver(post_save, sender=model, weak=False)
    def _post(sender, instance, created, **kwargs):
        snapshots = getattr(_cache, "snapshots", {})
        before = snapshots.pop(_key(instance), {}) if not created else {}
        after = _snapshot(instance)
        if not created and before == after:
            return  # no status / balance / lock change worth logging
        try:
            record_event(
                actor_id=None,  # populated by request middleware in Phase 9
                action=f"{action_prefix}.{'create' if created else 'update'}",
                target_type=sender.__name__,
                target_id=instance.pk,
                before=before,
                after=after,
            )
        except Exception as exc:
            # Never break the originating save because of audit logging.
            logger.exception("audit signal failed: %s", exc)


_register("escrow.EscrowTransaction", "escrow")
_register("payments.Payment", "payment")
_register("disputes.Dispute", "dispute")
