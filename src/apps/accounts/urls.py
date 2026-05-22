from rest_framework import permissions
from rest_framework_simplejwt.views import TokenRefreshView
from django.urls import path


from . import views as my_views


urlpatterns = [
    path('account/token/', my_views.CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('account/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('account/register/', my_views.RegistrationAPIView.as_view(), name='register'),
    path('account/users/me/', my_views.UserProfileRetrieveUpdateAPIView.as_view(), name='profile-retrieve-update'),
    path('account/users/change-password/', my_views.ChangePasswordAPIView.as_view(), name='change-password'),
    path('account/token/blacklist/', my_views.LogoutAPIView.as_view(), name='logout'),
    path('account/users/reset-password/', my_views.PasswordResetRequestAPIView.as_view(), name='password-reset-request'),
    path('account/users/reset-password/confirm/', my_views.PasswordResetConfirmAPIView.as_view(), name='password-reset-confirm'),
    path('account/admin/users/', my_views.UserListAPIView.as_view(), name='list-user'),
    path('account/users/me/deactivate/', my_views.UserDeleteAPIView.as_view(), name='deactivate-account'),
    path('account/reactivate/request/', my_views.ReactivationRequestAPIView.as_view(), name='account-reactivate-request'),
    path('account/reactivate/confirm/', my_views.AccountReactivationConfirmAPIView.as_view(), name='account-reactivate-confirm'),
]