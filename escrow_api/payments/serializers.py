from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
import uuid

from .models import Payment, PayoutMethod, ChapaPayoutMethod, StripePayoutMethod, Bank
from escrow.models import EscrowTransaction


class PaymentSerializer(serializers.ModelSerializer):
    milestone = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'escrow', 'user', 'amount', 'provider', 'transaction_type', 'status', 'provider_transactionn_id', 'milestone', 'timestamp']
        read_only_fields = fields


class FundingInitiateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    provider_name = serializers.CharField()


class FundingVerifySerializer(serializers.Serializer):
    tx_ref = serializers.CharField()


class ReleaseFundsSerializer(serializers.Serializer):
    escrow_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    milestone_id = serializers.IntegerField(required=False)


class RefundSerializer(serializers.Serializer):
    escrow_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    reason = serializers.CharField(required=False, allow_blank=True)


class PayoutMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutMethod
        fields = ['id', 'provider', 'is_default', 'is_verified', 'is_active', 'created_at', 'updated_at']

class ChapaPayoutMethodCreateSerializer(serializers.Serializer):
    account_name = serializers.CharField()
    account_number = serializers.CharField()
    bank_code = serializers.CharField()
    bank_name = serializers.CharField(required=False, allow_blank=True)
    is_default = serializers.BooleanField(default=False)

    def create(self, validated_data):
        user = self.context['request'].user
        with transaction.atomic():
            base = PayoutMethod.objects.create(user=user, provider='chapa', is_default=validated_data.pop('is_default', False))
            details = ChapaPayoutMethod.objects.create(payout_method=base, **validated_data)
        return base


class StripePayoutMethodCreateSerializer(serializers.Serializer):
    stripe_account_id = serializers.CharField()
    is_default = serializers.BooleanField(default=False)

    def create(self, validated_data):
        user = self.context['request'].user
        with transaction.atomic():
            base = PayoutMethod.objects.create(user=user, provider='stripe', is_default=validated_data.pop('is_default', False))
            details = StripePayoutMethod.objects.create(payout_method=base, **validated_data)
        return base


class SetPayoutMethodFlagsSerializer(serializers.Serializer):
    is_default = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = ['code', 'name', 'country']


class ChapaWebhookSerializer(serializers.Serializer):
    status = serializers.CharField(required=False, allow_blank=True)
    tx_ref = serializers.CharField(required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True)
    id = serializers.CharField(required=False, allow_blank=True)
    type = serializers.CharField(required=False, allow_blank=True)
    event = serializers.CharField(required=False, allow_blank=True)
    data = serializers.JSONField(required=False)

    def validate(self, attrs):
        payload = attrs.get('data') or {}

        event_hint = (
            attrs.get('event')
            or attrs.get('type')
            or payload.get('event')
            or payload.get('type')
            or ''
        )

        tx_ref = (
            attrs.get('tx_ref')
            or payload.get('tx_ref')
            or payload.get('transaction', {}).get('tx_ref')
        )

        transfer_reference = (
            attrs.get('reference')
            or payload.get('reference')
            or payload.get('transfer_reference')
            or payload.get('data', {}).get('reference')
        )

        if not tx_ref and not transfer_reference:
            raise serializers.ValidationError('Missing transaction or transfer reference in webhook payload')

        status_value = (
            attrs.get('status')
            or payload.get('status')
            or payload.get('data', {}).get('status')
            or payload.get('statusCode')
        )

        event_id = (
            attrs.get('id')
            or transfer_reference
            or tx_ref
            or f"chapa-{uuid.uuid4().hex}"
        )

        attrs['tx_ref'] = tx_ref
        attrs['transfer_reference'] = transfer_reference
        attrs['normalized_status'] = (status_value or '').lower()
        attrs['event_id'] = event_id
        attrs['event_type'] = (event_hint or ('transfer' if transfer_reference and not tx_ref else 'transaction')).lower()
        return attrs


