from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from . import models as my_models
from django.contrib.auth import authenticate


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        return token

    def validate(self, attrs):
        credentials = {
            'email': attrs.get('email'),
            'password': attrs.get('password')
        }

        user = authenticate(**credentials)

        if user is None:
            raise serializers.ValidationError("Invalid Credentials")
        
        data = super().validate(attrs)

        return data
    

class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    class Meta:
        model = my_models.CustomUser
        fields = ['first_name', 'last_name', 'user_type', 'phone_number', 'country', 'email', 'password', 'confirm_password']
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
            'country': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Password do not match.")
        
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = my_models.CustomUser.objects.create_user(**validated_data)

        return user
    

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = my_models.CustomUser
        fields = ('id', 'first_name', 'last_name', 'email', 'phone_number', 'user_type', 'country')
        read_only_fields = ('email',)