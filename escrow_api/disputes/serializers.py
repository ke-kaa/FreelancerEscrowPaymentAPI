from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from .models import Dispute, DisputeMessage
from escrow.models import EscrowTransaction


class DisputeCreateSerializer(serializers.ModelSerializer):
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
            escrow = getattr(project, 'escrowtransaction', None)
            if isinstance(escrow, EscrowTransaction):
                updates = []
                if not escrow.is_locked:
                    escrow.is_locked = True
                    updates.append('is_locked')
                if escrow.status != 'disputed':
                    escrow.status = 'disputed'
                    updates.append('status')
                if updates:
                    escrow.save(update_fields=updates)

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


class ModeratorDisputeUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for moderators to update a dispute's status and resolution.
    """
    class Meta:
        model = Dispute
        fields = ['status', 'resolution', 'moderator_note']

    def validate_status(self, value):
        if value not in ['resolved', 'closed']:
            raise serializers.ValidationError("Moderators can only set the status to 'resolved' or 'closed'.")
        return value

    def update(self, instance, validated_data):
        if instance.status != 'open':
            raise serializers.ValidationError(f"Cannot update a dispute with status '{instance.status}'.")

        status = validated_data.get('status')
        
        with transaction.atomic():
            instance.status = status
            instance.resolution = validated_data.get('resolution', instance.resolution)
            instance.moderator_note = validated_data.get('moderator_note', instance.moderator_note)
            
            if status == 'resolved':
                instance.resolved_by = self.context['request'].user
                instance.resolved_at = timezone.now()
                # # Unlock the project's escrow transaction if it exists
                # if hasattr(instance.project, 'escrotransaction'):
                #     escrow = instance.project.escrotransaction
                #     escrow.is_locked = False
                #     escrow.save(update_fields=['is_locked'])
            
            elif status == 'closed':
                instance.closed_at = timezone.now()

            instance.save()

            project = instance.project
            escrow = getattr(project, 'escrowtransaction', None)
            if isinstance(escrow, EscrowTransaction):
                updates = []
                if escrow.is_locked:
                    escrow.is_locked = False
                    updates.append('is_locked')
                if escrow.status == 'disputed':
                    escrow.status = 'funded' if escrow.current_balance > 0 else 'pending_funding'
                    updates.append('status')
                if updates:
                    escrow.save(update_fields=updates)

            if project.status == 'disputed':
                project.status = 'active'
                project.save(update_fields=['status'])
        
        return instance


class UpdateDisputeSerializer(serializers.ModelSerializer):
    """
    Serializer for the dispute owner to update the reason or type.
    """
    class Meta:
        model = Dispute
        fields = ['dispute_type', 'reason']

    def validate(self, attrs):
        if self.instance.status != 'open':
            raise serializers.ValidationError("Cannot edit a dispute that is no longer open.")
        return attrs

