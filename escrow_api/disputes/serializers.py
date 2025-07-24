from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from .models import Dispute, DisputeMessage


class CreateDisputeSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new dispute. Assumes the view provides 'project'
    and 'request' in the context.
    """
    raised_by = serializers.StringRelatedField(read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Dispute
        fields = ['id', 'dispute_type', 'reason', 'raised_by', 'status', 'created_at']
        read_only_fields = ['id', 'raised_by', 'status', 'created_at']

    def validate(self, attrs):
        """
        Validate that a dispute can be raised for the project.
        """
        project = self.context['project']

        if hasattr(project, 'dispute'):
            raise serializers.ValidationError("A dispute has already been raised for this project.")

        if project.status not in ['active', 'completed']:
             raise serializers.ValidationError(f"A dispute cannot be raised for a project with status '{project.status}'.")

        return attrs

    def create(self, validated_data):
        """
        Create the dispute and handle transactional side-effects.
        """
        project = self.context['project']
        
        with transaction.atomic():
            dispute = Dispute.objects.create(
                project=project,
                raised_by=self.context['request'].user,
                **validated_data
            )

            project.status = 'disputed'
            project.save(update_fields=['status'])

            # Lock the associated escrow transaction to prevent fund movement
            # if hasattr(project, 'escrotransaction'):
            #     escrow = project.escrotransaction
            #     escrow.is_locked = True
            #     escrow.save(update_fields=['is_locked'])

        return dispute


class DisputeDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieving a single dispute with all its details and messages.
    """
    project = serializers.StringRelatedField()
    raised_by = serializers.StringRelatedField()
    resolved_by = serializers.StringRelatedField()
    
    class Meta:
        model = Dispute
        fields = ['id', 'project', 'raised_by', 'dispute_type', 'reason', 'status', 'resolution', 'resolved_by', 'resolved_at', 'closed_at', 'moderator_note', 'created_at', 'updated_at',]
        read_only_fields = fields

