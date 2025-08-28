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



class EscrowReleaseSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    def validate(self, attrs):
        escrow: EscrowTransaction = self.context["escrow"]
        amount = attrs.get("amount", escrow.current_balance)

        if amount is None:
            amount = escrow.current_balance
        if amount <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if amount > escrow.current_balance:
            raise serializers.ValidationError("Amount exceeds available escrow balance.")
        attrs["amount"] = amount
        return attrs


class EscrowLockSerializer(serializers.Serializer):
    """Serializer to lock or unlock an escrow (e.g., during disputes)."""

    is_locked = serializers.BooleanField()

    def update(self, instance: EscrowTransaction, validated_data):
        instance.is_locked = validated_data["is_locked"]
        instance.save(update_fields=["is_locked"])
        return instance

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "is_locked": instance.is_locked,
            "status": instance.status,
        }
