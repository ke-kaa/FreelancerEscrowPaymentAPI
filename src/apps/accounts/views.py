from django.shortcuts import render
from rest_framework_simplejwt import views as jwt_views, tokens, authentication
from rest_framework import views as drf_Views, generics, permissions, status
from django.db import transaction
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


from . import serializers as my_serializers
from .utils import send_reset_email, generate_password_reset_link, send_reactivation_email, generate_reactivation_link
from . import models as my_models, throttles
from .pagination import UserListPagination
from . import permissions as my_permissions


class CustomTokenObtainPairView(jwt_views.TokenObtainPairView):
    serializer_class = my_serializers.CustomTokenObtainPairSerializer


class RegistrationAPIView(generics.CreateAPIView):
    """
    Handles new user registration.

    Accepts a POST request with user details:
        - email, password, confirm_password, first_name, last_name, country (required)
        - user_type, phone_number (optional)
    Creates a new user, and returns the user's data along with JWT access and
    refresh tokens.
    """
    serializer_class = my_serializers.RegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_summary="Register a new user",
        responses={
            201: my_serializers.RegistrationSerializer,
            400: "Invalid input"
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user = serializer.save()
            refresh = tokens.RefreshToken.for_user(user)

        return Response(
            {
                'user': serializer.data,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            },
            status=status.HTTP_201_CREATED
        )


class UserProfileRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """
    Allows authenticated users to retrieve and update their own profile.

    GET: Returns the profile of the currently authenticated user.
    PUT/PATCH: Updates the user's profile. The following fields are editable:
        - first_name, last_name, phone_number, country
    The 'id', 'email', and 'user_type' fields are read-only.
    """
    serializer_class = my_serializers.UserProfileSerializer
    authentication_classes = [authentication.JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(operation_summary="Retrieve user profile")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Update user profile")
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Partially update user profile")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_object(self):
        return self.request.user


class ChangePasswordAPIView(drf_Views.APIView):
    """
    Allows an authenticated user to change their password.

    Method: POST
    Request Body:
        - current password (required)
        - new password with confirmation (required)
    Validates the current password and ensures new passwords match before updating.
    """
    serializer_class = my_serializers.ChangePasswordSerializer
    authentication_classes = [authentication.JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Change the current user's password",
        request_body=my_serializers.ChangePasswordSerializer,
        responses={
            200: "Password updated successfully",
            400: "Invalid input"
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            serializer.update(request.user, serializer.validated_data)
            return Response({
                'detail': "Password updated successfully"
            }, status=status.HTTP_200_OK)
        return Response(serializer.error, status=status.HTTP_400_BAD_REQUEST)


class LogoutAPIView(drf_Views.APIView):
    """
    Allows an authenticated user to log out by blacklisting their refresh token.

    Method: POST
    Headers:
        - X-Refresh-Token (required)
    Blacklists the provided refresh token to invalidate the session.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="Log out the user by blacklisting their refresh token",
        manual_parameters=[
            openapi.Parameter(
                'X-Refresh-Token',
                openapi.IN_HEADER,
                description="Refresh token to blacklist",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: "Logout successful",
            400: "Invalid token"
        }
    )
    def post(self, request):
        refresh_token = request.headers.get('X-Refresh-Token')
        if not refresh_token:
            return Response({'detail': 'X-Refresh-Token header is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            token = tokens.RefreshToken(refresh_token)
            token.blacklist()
        except tokens.TokenError:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(
            {'detail': "Logout successful."},
            status=status.HTTP_200_OK
        )
    

class PasswordResetRequestAPIView(generics.GenericAPIView):
    """
    Allows users to request a password reset link via email.

    Method: POST
    Request Body:
        - email (required)
    Sends a password reset link to the provided email if the account exists.
    """
    serializer_class = my_serializers.PasswordResetRequestSerializer
    throttle_classes = [AnonRateThrottle,UserRateThrottle]
    permission_classes=[permissions.AllowAny]

    @swagger_auto_schema(
        operation_summary="Request a password reset email",
        request_body=my_serializers.PasswordResetRequestSerializer,
        responses={
            200: "Password reset link sent",
            400: "Invalid input"
        }
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.context['user']

        reset_url, _ = generate_password_reset_link(user)
        send_reset_email(user, reset_url)

        return Response(
            {'detail': "Check your email for a password reset link."},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmAPIView(generics.GenericAPIView):
    """
    Allows users to confirm and complete a password reset.

    Method: POST
    Request Body:
        - new_password (required)
        - confirm_password (required)
        - uid (required)
        - token (required)
    Validates the token and updates the user's password.
    """
    serializer_class = my_serializers.PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_summary="Confirm a password reset",
        request_body=my_serializers.PasswordResetConfirmSerializer,
        responses={
            200: "Password has been successfully updated",
            400: "Invalid token or input"
        }
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'success': "Password has been successfully updated."
        }, status=status.HTTP_200_OK)
    

class UserListAPIView(generics.ListAPIView):
    """
    Allows admin users to list all users with filtering and searching.

    Method: GET
    Query Parameters:
        - user_type (filter)
        - is_active (filter)
        - search (email, first_name, last_name)
        - ordering (id, last_name, first_name, user_type, created_at)
    Retrieves a paginated list of users.
    """
    serializer_class = my_serializers.UserListSerializer
    permission_classes = [permissions.IsAdminUser]
    
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user_type', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['id', 'last_name', 'first_name', 'user_type', 'created_at']
    ordering = ['-last_name', '-first_name']
    pagination_class = UserListPagination

    @swagger_auto_schema(
        operation_summary="List all users (Admin only)",
        responses={
            200: my_serializers.UserListSerializer(many=True),
            403: "Forbidden"
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return my_models.CustomUser.objects.all()
    

class UserDeleteAPIView(generics.UpdateAPIView):
    """
    Allows authenticated users to soft-delete their own account.

    Method: PATCH
    Headers:
        - X-Refresh-Token (optional)
    Sets the account as deleted and blacklists the refresh token if provided.
    """
    serializer_class = my_serializers.UserDeleteSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.JWTAuthentication]
    http_method_names = ['patch']

    def get_object(self):
        return self.request.user
    
    @swagger_auto_schema(
        operation_summary="Soft-delete the current user's account",
        manual_parameters=[
            openapi.Parameter(
                'X-Refresh-Token',
                openapi.IN_HEADER,
                description="Refresh token to blacklist (optional)",
                type=openapi.TYPE_STRING,
                required=False
            )
        ],
        responses={
            200: "Account deleted",
            400: "Invalid input"
        }
    )
    def update(self, request, *args, **kwargs):
        user = self.get_object()

        refresh_token = request.headers.get('X-Refresh-Token')
        if refresh_token:
            try:
                token = tokens.RefreshToken(refresh_token)
                token.blacklist()
            except tokens.TokenError:
                pass 
        
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'detail': "Account deleted."
        }, status=status.HTTP_200_OK)
    

class ReactivationRequestAPIView(generics.GenericAPIView):
    """
    Allows users to request an account reactivation link.

    Method: POST
    Request Body:
        - email (required)
    Sends a reactivation link if the account was deleted within the allowed time window.
    """
    serializer_class = my_serializers.ReactivationRequestSerializer
    permission_classes = [my_permissions.CanReactivate]
    throttle_classes = [throttles.EmailRateThrottle, AnonRateThrottle]

    @swagger_auto_schema(
        operation_summary="Request an account reactivation email",
        request_body=my_serializers.ReactivationRequestSerializer,
        responses={
            200: "Reactivation link sent",
            400: "Invalid input or permission denied"
        }
    )
    def post(self, request):
        seriailzer = self.get_serializer(data=request.data)
        seriailzer.is_valid(raise_exception=True)
        user = seriailzer.context['user']

        link, _, _ = generate_reactivation_link(user)
        send_reactivation_email(user, link)

        return Response({
            'detail': "Check your email to reactivate your account."
        }, status=status.HTTP_200_OK)
        

class AccountReactivationConfirmAPIView(generics.GenericAPIView):
    """
    Allows users to confirm and complete account reactivation.

    Method: POST
    Request Body:
        - uid (required)
        - token (required)
    Validates the token and restores the soft-deleted account.
    """
    serializer_class = my_serializers.AccountReactivationConfirmSerializer
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Confirm account reactivation",
    request_body=my_serializers.AccountReactivationConfirmSerializer,
        responses={
            200: "Account successfully reactivated",
            400: "Invalid token or input"
        }
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh_token = tokens.RefreshToken.for_user(user)

        return Response({
            'detail': "Account successfully reactivated.",
            'access': str(refresh_token.access_token),
            'refresh': str(refresh_token),
            'user': my_serializers.UserProfileSerializer(user).data
        }, status=status.HTTP_200_OK)
    

