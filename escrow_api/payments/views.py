from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
import logging

from .serializers import (
    PaymentSerializer,
    EscrowTransactionSerializer,
    FundingInitiateSerializer,
    FundingVerifySerializer,
    ReleaseFundsSerializer,
    RefundSerializer,
    PayoutMethodSerializer,
    ChapaPayoutMethodCreateSerializer,
    StripePayoutMethodCreateSerializer,
    SetPayoutMethodFlagsSerializer,
    BankSerializer,
    ChapaWebhookSerializer,
    StripeWebhookSerializer,
)
from .models import Payment, PayoutMethod, Bank, WebhookEvent
from escrow.models import EscrowTransaction
from escrow.services import EscrowService
from user_projects.models import UserProject
from .providers import get_payment_provider
from .tasks import task_transfer_to_freelancer, task_refund_to_client


logger = logging.getLogger(__name__)

class InitiateFundingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FundingInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(UserProject, id=serializer.validated_data['project_id'])
        escrow_service = EscrowService()
        result = escrow_service.initiate_funding(
            user=request.user,
            project=project,
            amount=serializer.validated_data['amount'],
            provider_name=serializer.validated_data['provider_name'],
        )
        code = status.HTTP_200_OK if result.get('status') == 'success' else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


