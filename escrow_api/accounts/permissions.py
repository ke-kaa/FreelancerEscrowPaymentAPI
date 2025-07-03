from rest_framework import permissions, response
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model


User = get_user_model()


class CanReactivate(permissions.BasePermission):
    def has_permission(self, request, view):
        try:
            user = User.objects.filter(email=request.email).first()
        except User.DoesNotExist:
            return response.Response({'detail': "This email is not registered"})
        
        allowed_window = timedelta(days=7)

        if not hasattr(user, 'deleted_at') or not user.deleted_at:
            return False
        
        time_since_deletion = timezone.now() - user.deleted_at

        return time_since_deletion <= allowed_window
        
        

