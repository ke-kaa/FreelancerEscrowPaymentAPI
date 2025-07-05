from rest_framework import serializers
from django.contrib.auth import get_user_model


from . import models as my_models


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number']


class ProposalSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = my_models.Proposal
        fields = ['id', 'big_ammount', 'cover_letter', 'status', 'submitted_at', 'estimated_delivery_days', 'is_withdrawn']


class CreateProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = my_models.UserProject
        fields = ['title', 'description', 'amount',]
    
    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Please enter a valid amount.")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user

        return my_models.UserProject.objects.create(
            client=user, 
            **validated_data
        )


class ListProjectAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = my_models.UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'status', 'commission_rate', 'created_at', 'updated_at']
    

class ListProjectClientSerializer(serializers.ModelSerializer):
    class Meta: 
        model = my_models.UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'commission_rate', 'status', 'created_at', 'updated_at', 'is_public']

    
class ListProjectFreelancerSerializer(serializers.ModelSerializer):
    class Meta: 
        model = my_models.UserProject
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
        model = my_models.UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'commission_rate', 'status', 'created_at', 'updated_at', 'is_public']
        read_only_fields = ('id', 'freelancer', 'commission_rate', 'status', 'updated_at', )


class RetrieveProjectFreelancerSerializer(serializers.ModelSerializer):
    client = UserSerializer(read_only=True)
    proposal = serializers.SerializerMethodField()
    
    class Meta:
        model = my_models.UserProject
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
        model = my_models.UserProject
        fields = ['id', 'client', 'freelancer', 'title', 'description', 'amount', 'comission_rate', 'status', 'created_at', 'updated_at', 'is_public']


class CreateProposalSerializer(serializers.ModelSerializer):
    class Meta:
        model = my_models.Proposal
        fields = ['cover_letter', 'bid_amount', 'estimated_delivery_days', 'is_withdrawn']
        extra_kwargs = {
            'bid_amount': {'required': True},
            'cover_letter': {'required': True}
        }

    def validate_bid_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Please enter a valid bid amount.")
        return value
    
    def validate(self, attrs):
        request = self.context['request']
        project = self.context['project']

        if my_models.Proposal.objects.filter(project=project, freelancer=request.user).exists():
            raise serializers.ValidationError("You have already submitted a proposal for this project.")


class ListProjectProposalClientSerializer(serializers.ModelSerializer):
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = my_models.Proposal
        fields = ['freelancer', 'bid_amount', 'submitted_at', 'status', 'estimated_delivery_days', 'is_withdrawn']


class RetrieveUpdateProposalClientSerializer(serializers.ModelSerializer):
    freelancer = UserSerializer(read_only=True)

    class Meta:
        model = my_models.Proposal
        fields = ['freelancer', 'cover_letter', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'client_note', 'estimated_delivery_days', 'is_withdrawn']
        read_only_fields = ('cover_letter', 'bid_amount', 'status', 'submitted_at', 'updated_at', 'estimated_delivery_days', 'is_withdrawn')