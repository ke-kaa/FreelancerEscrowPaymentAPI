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


class VerifyFundingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FundingVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        escrow_service = EscrowService()
        result = escrow_service.verify_funding(tx_ref=serializer.validated_data['tx_ref'])
        code = status.HTTP_200_OK if result.get('status') == 'success' else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class ReleaseFundsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ReleaseFundsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        escrow = get_object_or_404(EscrowTransaction, id=serializer.validated_data['escrow_id'])
        escrow_service = EscrowService()
        # ownership check (client only)
        if request.user.id != escrow.project.client_id:
            return Response({'status': 'error', 'message': 'Only the project client can release funds'}, status=status.HTTP_403_FORBIDDEN)
        # Enqueue async transfer
        task_transfer_to_freelancer.delay(
            escrow.id,
            str(serializer.validated_data.get('amount') or ''),
            serializer.validated_data.get('milestone_id')
        )
        result = {'status': 'success', 'message': 'Payout queued'}
        code = status.HTTP_200_OK if result.get('status') == 'success' else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)



class RefundView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        escrow = get_object_or_404(EscrowTransaction, id=serializer.validated_data['escrow_id'])
        escrow_service = EscrowService()
        # Enqueue async refund
        task_refund_to_client.delay(escrow.id, str(serializer.validated_data.get('amount') or ''), serializer.validated_data.get('reason', 'Project refund'))
        result = {'status': 'success', 'message': 'Refund queued'}
        code = status.HTTP_200_OK if result.get('status') == 'success' else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)


class EscrowDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, escrow_id):
        escrow = get_object_or_404(EscrowTransaction, id=escrow_id)
        data = EscrowTransactionSerializer(escrow).data
        return Response(data)


class EscrowPaymentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, escrow_id):
        escrow = get_object_or_404(EscrowTransaction, id=escrow_id)
        payments = Payment.objects.filter(escrow=escrow).order_by('-timestamp')
        data = PaymentSerializer(payments, many=True).data
        return Response(data)


class PayoutMethodListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        methods = PayoutMethod.objects.filter(user=request.user).order_by('-is_default', '-created_at')
        data = PayoutMethodSerializer(methods, many=True).data
        return Response(data)

    def post(self, request):
        provider = request.data.get('provider')
        if provider == 'chapa':
            serializer = ChapaPayoutMethodCreateSerializer(data=request.data, context={'request': request})
        elif provider == 'stripe':
            serializer = StripePayoutMethodCreateSerializer(data=request.data, context={'request': request})
        else:
            return Response({'detail': 'Unsupported provider'}, status=status.HTTP_400_BAD_REQUEST)
        serializer.is_valid(raise_exception=True)
        method = serializer.save()
        return Response(PayoutMethodSerializer(method).data, status=status.HTTP_201_CREATED)


class PayoutMethodDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, method_id):
        method = get_object_or_404(PayoutMethod, id=method_id, user=request.user)
        serializer = SetPayoutMethodFlagsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(method, field, value)
        method.save()
        return Response(PayoutMethodSerializer(method).data)

    def delete(self, request, method_id):
        method = get_object_or_404(PayoutMethod, id=method_id, user=request.user)
        method.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChapaBanksView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        provider = get_payment_provider('chapa')
        res = provider.get_banks()
        if res.get('status') == 'success':
            return Response({'banks': res.get('banks', [])})
        return Response(res, status=status.HTTP_400_BAD_REQUEST)


class StripeOnboardingLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .providers.stripe import StripeProvider
        account_id = request.data.get('stripe_account_id')
        provider = StripeProvider()
        if not account_id:
            return Response({'detail': 'stripe_account_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        link = provider.get_account_link(account_id)
        code = status.HTTP_200_OK if link.get('status') == 'success' else status.HTTP_400_BAD_REQUEST
        return Response(link, status=code)


class StripeWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = StripeWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_id = serializer.validated_data['id']

        if WebhookEvent.objects.filter(provider='stripe', event_id=event_id).exists():
            return Response({'status': 'duplicate'})

        event_type = serializer.validated_data['type']
        payment_intent_id = serializer.validated_data.get('payment_intent_id')
        transfer_id = serializer.validated_data.get('transfer_id')

        result = {'status': 'ignored', 'message': f'Unhandled event {event_type}'}

        if event_type == 'payment_intent.succeeded' and payment_intent_id:
            escrow_service = EscrowService()
            verification = escrow_service.verify_funding(tx_ref=payment_intent_id)
            result = {
                'status': verification.get('status'),
                'message': verification.get('message'),
                'escrow_id': verification.get('escrow_id'),
            }
        elif event_type == 'payment_intent.payment_failed' and payment_intent_id:
            payment = Payment.objects.filter(
                provider_transactionn_id=payment_intent_id,
                provider='stripe',
            ).first()
            if payment:
                payment.status = 'failed'
                payment.save(update_fields=['status'])
                result = {
                    'status': 'failed',
                    'message': 'Payment marked as failed',
                    'payment_id': payment.id,
                }
        elif event_type.startswith('transfer') and transfer_id:
            success_events = {'transfer.paid', 'transfer.succeeded', 'transfer.completed'}
            failure_events = {'transfer.failed', 'transfer.canceled', 'transfer.reversed'}
            if event_type in success_events or event_type in failure_events:
                logger.info(
                    "Processing Stripe transfer webhook",
                    extra={'transfer_id': transfer_id, 'event_type': event_type}
                )
                escrow_service = EscrowService()
                verification = escrow_service.verify_transfer_to_freelancer(
                    provider_name='stripe',
                    transfer_reference=transfer_id,
                    success=event_type in success_events,
                    details=request.data,
                )
                result = verification
        elif event_type.startswith('payout') and transfer_id:
            # Some Stripe accounts may emit payout.* events instead of transfer.*
            success_events = {'payout.paid', 'payout.succeeded'}
            failure_events = {'payout.failed', 'payout.canceled'}
            if event_type in success_events or event_type in failure_events:
                logger.info(
                    "Processing Stripe payout webhook",
                    extra={'transfer_id': transfer_id, 'event_type': event_type}
                )
                escrow_service = EscrowService()
                verification = escrow_service.verify_transfer_to_freelancer(
                    provider_name='stripe',
                    transfer_reference=transfer_id,
                    success=event_type in success_events,
                    details=request.data,
                )
                result = verification

        WebhookEvent.objects.create(provider='stripe', event_id=event_id)
        return Response(result)
