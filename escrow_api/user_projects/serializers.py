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