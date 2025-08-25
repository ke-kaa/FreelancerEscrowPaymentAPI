from decimal import Decimal

from rest_framework import serializers

from .models import EscrowTransaction
from payments.models import Payment


class PaymentSummarySerializer(serializers.ModelSerializer):
    milestone_id = serializers.IntegerField(source="milestone.id", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "transaction_type",
            "amount",
            "provider",
            "provider_transactionn_id",
            "milestone_id",
            "status",
            "timestamp",
        )
        read_only_fields = fields


class EscrowTransactionSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)
    client_id = serializers.IntegerField(source="project.client_id", read_only=True)
    client_email = serializers.EmailField(source="project.client.email", read_only=True)
    freelancer_id = serializers.IntegerField(source="project.freelancer_id", read_only=True)
    freelancer_email = serializers.EmailField(source="project.freelancer.email", read_only=True)
    payments = PaymentSummarySerializer(many=True, read_only=True)

    class Meta:
        model = EscrowTransaction
        fields = (
            "id",
            "project_id",
            "project_title",
            "client_id",
            "client_email",
            "freelancer_id",
            "freelancer_email",
            "funded_amount",
            "current_balance",
            "commission_amount",
            "is_locked",
            "status",
            "created_at",
            "updated_at",
            "payments",
        )
        read_only_fields = fields

