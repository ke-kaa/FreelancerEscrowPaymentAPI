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
    

class ListProjectClientSeriailzer(serializers.ModelSerializer):
    class Meta: 
        model = my_models.UserProject
        fields = ['client', 'freelancer', 'title', 'descrtiption', 'amount', 'commission_rate', 'status', 'created_at', 'updated_at', 'is_public']