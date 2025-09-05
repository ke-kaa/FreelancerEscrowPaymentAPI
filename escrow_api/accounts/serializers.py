from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.core.exceptions import ValidationError as DjangoPasswordValidationError


from .models import CustomUser


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer for user login and token generation.

    Fields:
        - email (required)
        - password (required)
    Validates credentials and checks if account is active before issuing tokens.
    """
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

        try:
            user = CustomUser.objects.filter(email=attrs.get('email')).first()
            if not user.is_active:
                raise AuthenticationFailed("Your account is deactivated. Reactivate to log in.")
        except:
            raise serializers.ValidationError("Invalid credentials")

        user = authenticate(**credentials)

        if user is None:
            raise serializers.ValidationError("Invalid Credentials")
        
        data = super().validate(attrs)

        return data
    

class RegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.

    Fields :
        required: first_name, last_name, user_type, country, email, password, confirm_password
        optional: phone_number
    Validates password confirmation and creates a new user.
    """
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'user_type', 'phone_number', 'country', 'email', 'password', 'confirm_password']
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
            'country': {'required': True},
            'user_type': {'required': True}
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Password do not match.")
        prospective_user = CustomUser(
            email=attrs.get('email'),
            first_name=attrs.get('first_name'),
            last_name=attrs.get('last_name'),
            user_type=attrs.get('user_type'),
            country=attrs.get('country'),
            phone_number=attrs.get('phone_number')
        )

        try:
            validate_password(attrs['password'], user=prospective_user)
        except DjangoPasswordValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)})

        return attrs
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = CustomUser.objects.create_user(**validated_data)

        return user
    

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile retrieval and updates.

    Fields:
        read-only: id, email, user_type
        - first_name, last_name, phone_number, country
    Handles profile data with read-only fields for security.
    """
    class Meta:
        model = CustomUser
        fields = ('id', 'first_name', 'last_name', 'email', 'phone_number', 'user_type', 'country')
        read_only_fields = ('id', 'email', 'user_type')


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing user password.

    Fields (all are required):
        - old_password 
        - new_password 
        - confirm_password
    Validates old password and ensures new passwords match.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        user = self.context['request'].user

        if not user.check_password(attrs['old_password']):
            raise serializers.ValidationError("Incorrect Password.")
        
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.DjangoValidationError("Passwords do not match.")

        try:
            validate_password(attrs['new_password'], user=user)
        except DjangoPasswordValidationError as exc:
            raise serializers.ValidationError({'new_password': list(exc.messages)})
        
        return attrs
        
    def update(self, instance, validated_data):
        instance.set_password(validated_data['new_password'])
        instance.save()

        return instance
    

class LogoutSerializer(serializers.Serializer):
    """
    Serializer for user logout.

    Fields:
        - refresh (required)
    Blacklists the provided refresh token to invalidate the session.
    """
    refresh = serializers.CharField()

    def validate(self, attrs):
        self.token = attrs['refresh']
        return attrs
    
    def save(self, **kwargs):
        try:
            token = RefreshToken(self.token)
            token.blacklist()
        except TokenError:
            raise serializers.ValidationError("Token is invalid or expired.")
        

class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.

    Fields:
        - email (required)
    Validates email and retrieves user for sending reset link.
    """
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("No account found with this email.")
        self.context['user'] = user
        return value
    

class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation.

    Fields (all are required):
        - new_password 
        - confirm_password 
        - uid 
        - token 
    Validates token and updates user password.
    """
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        
        try:
            uid = urlsafe_base64_decode(attrs['uid']).decode()
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            raise serializers.ValidationError("Invalid user.")

        if not PasswordResetTokenGenerator().check_token(user, attrs['token']):
            raise serializers.ValidationError("Invalid or expired token.")

        try:
            validate_password(attrs['new_password'], user=user)
        except DjangoPasswordValidationError as exc:
            raise serializers.ValidationError({'new_password': list(exc.messages)})
    
        attrs['user'] = user     
        return attrs
    
    def save(self, **kwargs):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()

        return user
    

class UserListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing users.

    Fields (all read-only):
        - id
        - email
        - first_name
        - last_name
        - user_type
        - is_active
        - created_at
        - updated_at
        - deleted_at
    Provides user data for administrative listing.
    """
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'user_type', 'is_active', 'created_at', 'updated_at', 'deleted_at']


class UserDeleteSerializer(serializers.ModelSerializer):
    """
    Serializer for soft deleting users.

    Fields:
        - id (read-only)
        - email (read-only)
        - is_active (read-only after update)
        - deleted_at (read-only, set on update)
    Performs soft delete by setting deleted_at timestamp and deactivating user.
    """
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'is_active', 'deleted_at']
        read_only_fields = ['id', 'email', 'deleted_at']
    
    def update(self, instance, validated_data):
        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save()
        return instance
    

class ReactivationRequestSerializer(serializers.Serializer):
    """
    Serializer for account reactivation request.

    Fields:
        - email (required)
    Validates email and ensures the account is deactivated before allowing reactivation request.
    """
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = CustomUser.objects.filter(email=value).first()
        except:
            raise serializers.ValidationError("No user found with this email.")
        
        if user.is_active or not user.deleted_at:
            raise serializers.ValidationError("This account is not deactivated.")
        
        self.context['user'] = user

        return value
    

class AccountReactivationConfrimSerailizer(serializers.Serializer):
    """
    Serializer for account reactivation confirmation.

    Fields (all required):
        - uid
        - token
    Validates reactivation token and reactivates the user account.
    """
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            raise serializers.ValidationError("Invalid reactivation link.")
        
        token = attrs.get('token')
        if not PasswordResetTokenGenerator().check_token(user, token):
            raise serializers.ValidationError("Invalid or expired token.")
        
        if user.is_active or user.deleted_at is None:
            raise serializers.ValidationError("This account is already active.")
        
        self.context['user'] = user
        return attrs
    
    def save(self):
        user = self.context['user']
        user.is_active = True
        user.deleted_at = None
        user.save()
        return user