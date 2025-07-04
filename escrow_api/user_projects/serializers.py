from rest_framework import serializers


from . import models as my_models


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


class RetrieveUpdateDeleteProjectClientSeriailzer(serializers.ModelSerializer):
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