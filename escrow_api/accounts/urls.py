from rest_framework import permissions
from rest_framework_simplejwt.views import TokenRefreshView
from django.urls import path


from . import views as my_views


urlpatterns = [
    path('api/token/', my_views.CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('api/register/', my_views.RegistrationAPIView.as_view(), name='register'),
    path('api/users/me/', my_views.UserProfileRetrieveUpdateAPIView.as_view(), name='profile-retrieve-update'),
    path('api/users/change-password/', my_views.ChangePasswordAPIView.as_view(), name='change-password'),
    path('api/token/blacklist/', my_views.LogoutAPIView.as_view(), name='logout'),
    path('api/users/reset-password/', my_views.PasswordResetRequestAPIView.as_view(), name='password-reset-request'),
    path('api/users/reset-password/confirm/', my_views.PasswordResetConfirmAPIView.as_view(), name='password-reset-confirm'),
    path('api/admin/users/', my_views.UserListAPIView.as_view(), name='list-user'),
    path('api/users/me/deactivate/', my_views.UserDeleteAPIView.as_view(), name='deactivate-account'),
    path('api/reactivate/request/', my_views.ReactivationRequestAPIView.as_view(), name='account-reactivate-request'),
    path('api/reactivate/confirm/', my_views.AccountReactivationConfirmAPIView.as_view(), name='account-reactivate-confirm'),
]