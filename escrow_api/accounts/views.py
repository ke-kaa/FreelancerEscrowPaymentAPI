from django.shortcuts import render
from rest_framework_simplejwt import views as jwt_views, tokens, authentication
from rest_framework import views as drf_Views, generics, permissions, response, status
from django.db import transaction


from . import serializers as my_serializers


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

        return response.Response(
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

