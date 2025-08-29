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

