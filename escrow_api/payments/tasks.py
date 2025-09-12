from celery import shared_task
import logging

from django.db import transaction
from django.contrib.auth import get_user_model

from escrow.services import EscrowService
from escrow.models import EscrowTransaction
from user_projects.models import Milestone

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def task_transfer_to_freelancer(escrow_id: int, amount_str: str, milestone_id: int | None = None):
    try:
        escrow = EscrowTransaction.objects.select_related('project', 'project__freelancer').get(id=escrow_id)
        service = EscrowService()
        # amount is re-validated in release_funds; this task is generic
        milestone = None
        if milestone_id:
            milestone = Milestone.objects.filter(id=milestone_id, project=escrow.project).first()
        result = service.release_funds(
            escrow=escrow,
            amount=None if not amount_str else amount_str,
            milestone=milestone,
        )
        return result
    except Exception as e:
        logger.error(f"task_transfer_to_freelancer failed: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def task_refund_to_client(escrow_id: int, amount_str: str, reason: str = "Project refund"):
    try:
        escrow = EscrowTransaction.objects.select_related('project', 'project__client').get(id=escrow_id)
        service = EscrowService()
        # Backend-driven refunds should specify the acting user; for cron/moderator use client
        user = escrow.project.client
        result = service.refund(user=user, escrow=escrow, amount=None if not amount_str else amount_str, reason=reason)
        return result
    except Exception as e:
        logger.error(f"task_refund_to_client failed: {str(e)}")
        return {"status": "error", "message": str(e)}



