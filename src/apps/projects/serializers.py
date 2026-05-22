from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.utils.timezone import timedelta


from .utils import send_proposal_accept_email
from .models import UserProject, Proposal, Milestone, Review
from .constants import REVIEW_UPDATE_WINDOW_DAYS


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for lightweight user references.

    Fields (all read-only): id, first_name, last_name, email, phone_number.
    Used when embedding client/freelancer details in project and proposal payloads.
    """
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number']


class ProposalSummarySerializer(serializers.ModelSerializer):
    """
    Serializer summarizing proposal submissions for list/detail views.

    Fields (all read-only): id, bid_amount, cover_letter, status, submitted_at,
    estimated_delivery_days, is_withdrawn.
    """
    class Meta:
        model = Proposal
        fields = ['id', 'bid_amount', 'cover_letter', 'status', 'submitted_at', 'estimated_delivery_days', 'is_withdrawn']


class ProjectSummarySerializer(serializers.ModelSerializer):
    """
    Serializer providing compact project information for nested responses.

    Fields (all read-only): id, title, description, amount, created_at, status.
    """
    class Meta:
        model = UserProject
        fields = ['id', 'title', 'description', 'amount', 'created_at', 'status']


class MilestoneSummarySeriailzer(serializers.ModelSerializer):
    """
    Serializer outlining milestone progress and payment status.

    Fields (all read-only): id, title, description, amount, status, submitted_at,
    approved_at, rejected_reason, due_date, is_paid.
    """
    class Meta:
        model = Milestone
        fields = ['id', 'title', 'description', 'amount', 'status', 'submitted_at', 'approved_at', 'rejected_reason', 'due_date', 'is_paid']


class CreateProjectClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients to create new projects.

    Fields:
        - title, description, amount (required inputs)
    Automatically attaches the authenticated client to the project record.
    """
    class Meta:
        model = UserProject
        fields = ['title', 'description', 'amount',]
    
    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Please enter a valid amount.")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user

        return UserProject.objects.create(
            client=user, 
            **validated_data
        )


class ListProjectAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for administrators listing all projects.

    Fields include project participants, financials, and timestamps to support back-office overview.
    """
    class Meta:
        model = UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'status', 'commission_rate', 'created_at', 'updated_at']
    

class ListProjectClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients listing their own projects.

    Exposes participant info, commission rate, visibility flag, and lifecycle metadata.
    """
    class Meta: 
        model = UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'commission_rate', 'status', 'created_at', 'updated_at', 'is_public']

    
class ListProjectFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer for freelancers listing projects they are assigned to.

    Includes embedded client summary plus project scope, pay, and status fields.
    """
    client = UserSerializer(read_only=True)

    class Meta: 
        model = UserProject
        fields = ['id', 'client', 'title', 'freelancer', 'description', 'amount', 'commission_rate', 'status', 'created_at', 'updated_at']


class RetrieveUpdateDeleteProjectClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients retrieving/updating their project details.

    Provides structured client/freelancer contact info and enforces read-only contract attributes.
    """
    client = serializers.SerializerMethodField()
    freelancer = serializers.SerializerMethodField()

    def get_client(self, obj):
        return {
            'name': obj.client.get_full_name(),
            'email': obj.client.email
        }
    
    def get_freelancer(self, obj):
        if obj.freelancer:
            return {
                'name': obj.freelancer.get_full_name(),
                'email': obj.freelancer.email
            }
        return None
        
    class Meta:
        model = UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'commission_rate', 'status', 'created_at', 'updated_at', 'is_public']
        read_only_fields = ('id', 'freelancer', 'commission_rate', 'status', 'updated_at', )


class RetrieveProjectFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer for freelancers viewing a specific project.

    Includes client summary and the freelancer's proposal context, if submitted.
    """
    client = UserSerializer(read_only=True)
    proposal = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProject
        fields = ['client', 'title', 'description', 'amount', 'status', 'created_at', 'updated_at', 'proposal']

    def get_proposal(self, obj):
        user = self.context['request'].user
        proposal = obj.proposals.filter(freelancer=user).first()

        if proposal:
            return ProposalSummarySerializer(proposal).data
        return None


class RetrieveProjectAdminSeriailzer(serializers.ModelSerializer):
    """
    Serializer for administrators reviewing individual projects with participant details.
    """
    client = UserSerializer(read_only=True)
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'comission_rate', 'status', 'created_at', 'updated_at', 'is_public']


class CreateProposalFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer for freelancers submitting proposals.

    Validates positive bid amount and prevents duplicate submissions per project/user pair.
    """
    class Meta:
        model = Proposal
        fields = ['cover_letter', 'bid_amount', 'estimated_delivery_days', 'is_withdrawn']
        extra_kwargs = {
            'bid_amount': {'required': True},
            'cover_letter': {'required': True},
            'estimated_delivery_days': {'required': True}
        }

    def validate_bid_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Please enter a valid bid amount.")
        return value
    
    def validate(self, attrs):
        request = self.context['request']
        project = self.context['project']

        if Proposal.objects.filter(project=project, freelancer=request.user).exists():
            raise serializers.ValidationError("You have already submitted a proposal for this project.")
        
        return attrs


class ListProjectProposalsClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients listing proposals received on a project.

    Embeds freelancer contact info and key bid metadata.
    """
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ['id', 'freelancer', 'bid_amount', 'submitted_at', 'status', 'estimated_delivery_days', 'is_withdrawn']


class RetrieveUpdateProposalClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients reviewing a single proposal.

    Exposes freelancer details and renders proposal content read-only post submission.
    """
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ['freelancer', 'cover_letter', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'client_note', 'estimated_delivery_days', 'is_withdrawn']
        read_only_fields = ('cover_letter', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'estimated_delivery_days', 'is_withdrawn')


class AcceptProposalClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients recording proposal acceptance.

    Returns freelancer summary alongside acceptance timestamp.
    """
    freelancer = UserSerializer(read_only=True)
    class Meta:
        model = Proposal
        fields = ['id', 'freelancer', 'status', 'accepted_at',]
        read_only_fields = ['id', 'status', 'acceptegd_at']
    

class RejectProposalClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients tracking rejected proposals.

    Provides freelancer and project context with final status.
    """
    freelancer = UserSerializer(read_only=True)
    project = ProjectSummarySerializer(read_only=True)
    
    class Meta:
        model = Proposal
        fields = ['id', 'freelancer', 'project', 'updated_at', 'status']
        read_only_fields = ['id', 'freelancer', 'project', 'status', 'updated_at']


class ListProposalsFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer for freelancers listing proposals they have submitted.

    Includes project summary and proposal lifecycle metadata.
    """
    project = ProjectSummarySerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ['id', 'project', 'cover_letter', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'estimated_delivery_days', 'is_seen_by_client', 'is_withdrawn']


class RetrieveUpdateProposalFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer for freelancers viewing/updating their proposals (where editable).

    Enforces non-negative updates for bid amount and delivery days while keeping immutable fields read-only.
    """
    project = ProjectSummarySerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            'id', 'project', 'cover_letter', 'bid_amount', 'status', 'submitted_at',
            'updated_at', 'estimated_delivery_days', 'is_seen_by_client', 'is_withdrawn',
            'client_note', 'accepted_at'
        ]
        read_only_fields = (
            'id', 'status', 'submitted_at', 'updated_at', 'is_seen_by_client',
            'is_withdrawn', 'client_note', 'accepted_at'
        )
    
    def validate(self, attrs):
        if attrs.get('bid_amount', 0) < 0:
            raise serializers.ValidationError("Please enter acceptable bid amount.")
        if attrs.get('estimated_delivery_days', 0) < 0:
            raise serializers.ValidationError("Please enter valid delivery days.")
        
        return attrs
    
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


class WithdrawProposalFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer presenting minimal data when freelancers view withdrawn proposals.

    All fields are read-only to emphasize historical state.
    """
    project = serializers.StringRelatedField()
    class Meta:
        model = Proposal
        fields = ['id', 'project', 'is_withdrawn', 'status']
        read_only_fields = ['id', 'project', 'is_withdrawn', 'status']


class ListProjectProposalsAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for administrators auditing proposals across projects.

    Combines project, freelancer, and bidding details for oversight tasks.
    """
    project = ProjectSummarySerializer(read_only=True)
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ['id', 'project', 'freelancer', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'estimated_delivery_days', 'is_seen_by_client', 'is_withdrawn', 'accepted_at']


class CreateMilestoneClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients creating project milestones.

    Validates project context, permissions, and project status prior to creation.
    """
    class Meta:
        model = Milestone
        fields = ['title', 'description', 'amount', 'due_date']

    def validate(self, attrs):
        project = self.context.get('project')
        request = self.context.get('request')
        if not project:
            raise serializers.ValidationError("Project context is missing.")
        if project.client != request.user:
            raise serializers.ValidationError("You do not have permission to add milestones to this project.")
        if project.status not in ['pending', 'active']:
            raise serializers.ValidationError("Cannot add milestones to a project that is not active or pending.")
        return attrs

    def create(self, validated_data):
        project = self.context['project']
        return Milestone.objects.create(project=project, **validated_data)


class ListProjectMilestonesClientFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer for listing milestones to both clients and freelancers.

    Details milestone progress, payment flags, and timeline metadata.
    """
    class Meta:
        model = Milestone
        fields = ['id', 'project', 'title', 'description', 'amount', 'status', 'submitted_at', 'approved_at', 'rejected_reason', 'due_date', 'is_paid']


class SubmitMilestoneFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer enabling freelancers to submit work for milestone review.

    Ensures only pending milestones can transition to submitted status.
    """
    class Meta:
        model = Milestone
        fields = ['status']
        read_only_fields = ['status']

    def update(self, instance, validated_data):
        if instance.status != 'pending':
            raise serializers.ValidationError("Only pending milestones can be submitted.")
        instance.status = 'submitted'
        instance.submitted_at = timezone.now()
        instance.save(update_fields=['status', 'submitted_at'])
        return instance
    

class RetrieveUpdateDeleteMilestoneClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients to review or update pending milestones.

    Keeps submission/audit metadata read-only while permitting scope edits prior to approval.
    """
    project = ProjectSummarySerializer(read_only=True)

    class Meta:
        model = Milestone
        fields = ['id', 'project', 'title', 'description', 'amount', 'due_date','status', 'submitted_at', 'approved_at', 'rejected_reason', 'is_paid']
        read_only_fields = ['id', 'project', 'submitted_at', 'approved_at', 'rejected_reason', 'is_paid']


    def update(self, instance, validated_data):
        if instance.status != 'pending':
            raise serializers.ValidationError("Only pending milestones can be updated.")
        
        for attr in ['title', 'description', 'amount', 'due_date']:
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])

        instance.save()
        return instance


class RetrieveMilestoneFreelancerSerializer(serializers.ModelSerializer):
    """
    Serializer for freelancers viewing milestone details and status history.

    All fields read-only to reflect authoritative milestone records.
    """
    project = ProjectSummarySerializer(read_only=True)

    class Meta:
        model = Milestone
        fields = ['id', 'project', 'title', 'description', 'amount', 'due_date', 'status', 'submitted_at', 'approved_at', 'rejected_reason', 'is_paid']
        read_only_fields = ['id', 'project', 'title', 'description', 'amount', 'due_date', 'submitted_at', 'approved_at', 'rejected_reason', 'is_paid']
    

class ApproveMilestoneClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients approving submitted milestones.

    Updates status and timestamp upon validation.
    """
    class Meta:
        model = Milestone
        fields = ['status']

    def update(self, instance, validated_data):
        if instance.status != 'submitted':
            raise serializers.ValidationError("Only submitted milestones can be approved.")
        
        instance.status = 'approved'
        instance.approved_at = timezone.now()
        # TODO: Trigger escrow release here if needed
        instance.save(update_fields=['status', 'approved_at'])
        
        return instance


class RejectMilestoneClientSerializer(serializers.ModelSerializer):
    """
    Serializer for clients rejecting submitted milestones with a mandatory reason.
    """
    class Meta:
        model = Milestone
        fields = ['status', 'rejected_reason']

    def update(self, instance, validated_data):
        if instance.status != 'submitted':
            raise serializers.ValidationError("Only submitted milestones can be rejected.")
        reason = validated_data.get('rejected_reason')
        if not reason:
            raise serializers.ValidationError("Rejection reason must be provided.")
        instance.status = 'rejected'
        instance.rejected_reason = reason
        instance.save(update_fields=['status', 'rejected_reason'])
        
        return instance


class CreateReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for creating project reviews (client ↔ freelancer).

    Validates project completion status, review window, and duplicate submissions.
    """
    class Meta:
        model = Review
        fields = ['project', 'review_type', 'rating', 'communication', 'quality', 'professionalism', 'comment', 'private_comment']
        read_only_fields = ['project', 'review_type']

    def validate(self, attrs):
        user = self.context['request'].user
        project = self.context['project']
        review_type = self.context['review_type']

        if project.status != 'completed' or not project.completed_at:
            raise serializers.ValidationError("Reviews can only be submitted for completed projects.")

        review_deadline = project.completed_at + timedelta(days=14)
        if timezone.now() > review_deadline:
            raise serializers.ValidationError("Review period has expired.")

        if Review.objects.filter(project=project, reviewer=user, review_type=attrs['review_type']).exists():
            raise serializers.ValidationError("You have already submitted this review.")

        return attrs

    def create(self, validated_data):
        validated_data['reviewer'] = self.context['request'].user
        validated_data['reviewee'] = self.context['reviewee']
        validated_data['project'] = self.context['project']
        validated_data['review_type'] = self.context['review_type']
        
        return super().create(validated_data)


class RetrieveProjectReviewSerializer(serializers.ModelSerializer):
    """
    Serializer rendering submitted reviews with human-readable relations.
    """
    reviewer = serializers.StringRelatedField()
    reviewee = serializers.StringRelatedField()
    project = serializers.StringRelatedField()

    class Meta:
        model = Review
        fields = ['id', 'project', 'reviewer', 'reviewee', 'review_type', 'rating', 'communication', 'quality', 'professionalism', 'comment', 'created_at']
        read_only_fields = fields


class UpdateProjectReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for updating reviews within the allowed edit window.

    Allows adjusting ratings and comments while enforcing the deadline constraint.
    """
    class Meta:
        model = Review
        fields = [
            'rating',
            'communication',
            'quality',
            'professionalism',
            'comment',
            'private_comment',
        ]

    def validate(self, attrs):
        review = self.instance
        deadline = review.created_at + timedelta(days=REVIEW_UPDATE_WINDOW_DAYS)
        if timezone.now() > deadline:
            raise serializers.ValidationError("You can no longer update this review.")
        return attrs

