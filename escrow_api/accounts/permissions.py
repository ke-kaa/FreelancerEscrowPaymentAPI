from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, NotFound
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model


User = get_user_model()


class CanReactivate(permissions.BasePermission):
    """
    Permission class to control account reactivation requests.

    Logic:
    - Requires an 'email' in the request data.
    - Checks if a user with the given email exists.
    - Only allows reactivation if the account was deleted within the last 7 days.
    - Denies if the account is already active or the reactivation window has expired.
    - Raises appropriate DRF exceptions for missing email, user not found, already active, or expired window.
    """
    def has_permission(self, request, view):
        email = (request.data or {}).get('email')
        if not email:
            raise PermissionDenied("Email is required to request reactivation.")

        user = User.objects.filter(email=email).first()
        if not user:
            raise NotFound("This email is not registered.")
        
        allowed_window = timedelta(days=7)

        if not getattr(user, 'deleted_at', None):
            raise PermissionDenied("Account is already active.")
        
        time_since_deletion = timezone.now() - user.deleted_at

        if time_since_deletion > allowed_window:
            raise PermissionDenied("Reactivation window has expired.")

        return True
        
        