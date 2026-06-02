import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.escrow.models import EscrowTransaction
from apps.escrow.services import EscrowService

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def task_transfer_to_freelancer(escrow_id: int, amount_str: str, milestone_id: int | None = None):
    try:
        service = EscrowService()
        return service.release_funds(
            escrow_id=escrow_id,
            amount=None if not amount_str else amount_str,
            milestone_id=milestone_id,
        )
    except Exception as e:
        logger.error("task_transfer_to_freelancer failed: %s", e)
        return {"status": "error", "message": str(e)}


@shared_task
def task_refund_to_client(escrow_id: int, amount_str: str, reason: str = "Project refund"):
    try:
        escrow = EscrowTransaction.objects.select_related("project", "project__client").get(id=escrow_id)
        service = EscrowService()
        return service.refund(
            user=escrow.project.client,
            escrow_id=escrow_id,
            amount=None if not amount_str else amount_str,
            reason=reason,
        )
    except Exception as e:
        logger.error("task_refund_to_client failed: %s", e)
        return {"status": "error", "message": str(e)}
