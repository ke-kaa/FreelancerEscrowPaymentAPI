from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .utils import send_proposal_accept_email
from django.db import transaction


from .models import UserProject, Proposal, Milestone, Review


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number']


class ProposalSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Proposal
        fields = ['id', 'big_ammount', 'cover_letter', 'status', 'submitted_at', 'estimated_delivery_days', 'is_withdrawn']


class ProjectSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProject
        fields = ['id', 'title', 'description', 'amount', 'created_at', 'status']


class CreateProjectClientSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'status', 'commission_rate', 'created_at', 'updated_at']
    

class ListProjectClientSerializer(serializers.ModelSerializer):
    class Meta: 
        model = UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'commission_rate', 'status', 'created_at', 'updated_at', 'is_public']

    
class ListProjectFreelancerSerializer(serializers.ModelSerializer):
    class Meta: 
        model = UserProject
        fields = ['id', 'client', 'title', 'freelancer', 'description', 'amount', 'commission_rate', 'status', 'created_at', 'updated_at']


class RetrieveUpdateDeleteProjectClientSerializer(serializers.ModelSerializer):
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
    client = UserSerializer(read_only=True)
    proposal = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProject
        fields = ['client', 'title', 'description', 'amount', 'status', 'created_at', 'updated_at']

    def get_proposal(self, obj):
        user = self.context['request'].user
        proposal = obj.proposals.filter(freelancer=user)

        if proposal:
            return ProposalSummarySerializer(proposal).data
        return None


class RetrieveProjectAdminSeriailzer(serializers.ModelSerializer):
    client = UserSerializer(read_only=True)
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'comission_rate', 'status', 'created_at', 'updated_at', 'is_public']


class CreateProposalFreelancerSerializer(serializers.ModelSerializer):
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


class ListProjectProposalsClientSerializer(serializers.ModelSerializer):
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ['freelancer', 'bid_amount', 'submitted_at', 'status', 'estimated_delivery_days', 'is_withdrawn']


class RetrieveUpdateProposalClientSerializer(serializers.ModelSerializer):
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ['freelancer', 'cover_letter', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'client_note', 'estimated_delivery_days', 'is_withdrawn']
        read_only_fields = ('cover_letter', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'estimated_delivery_days', 'is_withdrawn')


class AcceptProposalClientSerializer(serializers.ModelSerializer):
    freelancer = UserSerializer(read_only=True)
    class Meta:
        model = Proposal
        fields = ['id', 'freelancer', 'status', 'accepted_at',]
        read_only_fields = ['id', 'status', 'acceptegd_at']
    

class RejectProposalClientSerializer(serializers.ModelSerializer):
    freelancer = UserSerializer(read_only=True)
    project = ProjectSummarySerializer(read_only=True)
    
    class Meta:
        model = Proposal
        fields = ['id', 'freelancer', 'project', 'updated_at', 'status']
        read_only_fields = ['id', 'freelancer', 'project', 'status', 'updated_at']
   

class ListProposalsFreelancerSerializer(serializers.ModelSerializer):
    project = ProjectSummarySerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ['id', 'project', 'cover_letter', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'estimated_delivery_days', 'is_seen_by_client', 'is_withdrawn']


class RetrieveUpdateProposalFreelancerSerializer(serializers.ModelSerializer):
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
    project = serializers.StringRelatedField()
    class Meta:
        model = Proposal
        fields = ['id', 'project', 'is_withdrawn', 'status']
        read_only_fields = ['id', 'project', 'is_withdrawn', 'status']


class ListProjectProposalsAdminSerializer(serializers.ModelSerializer):
    project = ProjectSummarySerializer(read_only=True)
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ['id', 'project', 'freelancer', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'estimated_delivery_days', 'is_seen_by_client', 'is_withdrawn', 'accepted_at']


class CreateMilestoneClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ['project', 'title', 'description', 'amount', 'due_date']

    def validate(self, attrs):
        project = attrs.get('project')
        request = self.context['request']
        if project.client != request.user:
            raise serializers.ValidationError("You do not have permission to add milestones to this project.")
        if project.status not in ['pending', 'active']:
            raise serializers.ValidationError("Cannot add milestones to a project that is not active or pending.")
        return attrs
    

class ListProjectMilestonesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ['id', 'project', 'title', 'description', 'amount', 'status', 'submitted_at', 'approved_at', 'reject_reason', 'due_date', 'is_paid']

