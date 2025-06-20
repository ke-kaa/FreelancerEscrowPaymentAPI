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
            'passowrd': attrs.get('password')
        }

        user = authenticate(**credentials)

        if user is None:
            raise serializers.ValidationError("Invalid Credentials")
        
        data = super().validate(attrs)

        return data
    

class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = my_models.CustomUser
        fields = ['user_type', 'phone_number', 'country', 'email', 'passowrd', 'confirm_password']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_passowrd']:
            raise serializers.ValidationError("Password do not match.")
        
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = my_models.CustomUser.objects.create(**validated_data)

        return user