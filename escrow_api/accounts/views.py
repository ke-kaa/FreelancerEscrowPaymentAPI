from django.shortcuts import render
from rest_framework_simplejwt import views as jwt_views, tokens, authentication
from rest_framework import views as drf_Views, generics, permissions, status
from django.db import transaction
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter


from . import serializers as my_serializers
from .utils import send_reset_email, generate_password_reset_link
from . import models as my_models
from .pagination import UserListPagination


class CustomTokenObtainPairView(jwt_views.TokenObtainPairView):
    serializer_class = my_serializers.CustomTokenObtainPairSerializer


class RegistrationAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.RegistrationSerializer
    permission_classes = [permissions.AllowAny]

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
    serializer_class = my_serializers.UserProfileSerializer
    authentication_classes = [authentication.JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    

class ChangePasswordAPIView(generics.UpdateAPIView):
    serializer_class = my_serializers.ChangePasswordSerializer
    authentication_classes = [authentication.JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LogoutAPIView(drf_Views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = my_serializers.LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {'detail': "Logout successful."},
            status=status.HTTP_200_OK
        )
    

class PasswordResetRequestAPIView(generics.GenericAPIView):
    '''
    Accepts POST request with user's email.
    Sends an email using send_reset_email function (defined in utils.py)
    send_reset_email sends an email containing uid and token for password reset which are expected
        by the PasswordResetConfirmView
    '''
    serializer_class = my_serializers.PasswordResetRequestSerializer
    throttle_classes = [AnonRateThrottle,UserRateThrottle]
    permission_classes=[permissions.AllowAny]

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
    '''
    Accepts POST request with uidb65, token, new_password, confirm_password'''
    serializer_class = my_serializers.PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'success': "Password has been successfully updated."
        }, status=status.HTTP_200_OK)
    

class UserListAPIView(generics.ListAPIView):
    serializer_class = my_serializers.UserListSerializer
    permission_classes = [permissions.IsAdminUser]
    
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user_type', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['id', 'last_name', 'first_name', 'user_type', 'created_at']
    ordering = ['-last_name', '-first_name']
    pagination_class = UserListPagination

    def get_queryset(self):
        return my_models.CustomUser.objects.all()
    

class UserDeleteAPIView(generics.UpdateAPIView):
    serializer_class = my_serializers.UserDeleteSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.JWTAuthentication]
    http_method_names = ['patch']

    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        user = self.get_object()

        try: 
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = tokens.RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass
        
        serializer = self.get_serializer(user, data=request.data, patial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'detail': "Account deleted."
        }, status=status.HTTP_200_OK)

