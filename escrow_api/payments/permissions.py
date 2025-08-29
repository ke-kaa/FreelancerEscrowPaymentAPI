from rest_framework.permissions import BasePermission


class IsOwnerClient(BasePermission):
    """Allow only the project client to act on escrow/payment objects."""
    def has_object_permission(self, request, view, obj):
        escrow = getattr(obj, 'escrow', obj)
        project = getattr(escrow, 'project', None)
        return project and request.user.id == project.client_id


class IsModerator(BasePermission):
    """Placeholder for moderator role; integrate with your groups/permissions."""
    def has_permission(self, request, view):
        return request.user and request.user.is_staff

