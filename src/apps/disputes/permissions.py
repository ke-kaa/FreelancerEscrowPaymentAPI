from rest_framework.permissions import BasePermission
from .models import Dispute

class IsModerator(BasePermission):
    """
    Allows access only to users in the 'Moderators' group.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.groups.filter(name='Moderators').exists()


class IsDisputeParticipantOrModerator(BasePermission):
    """
    Allows access only to the project's client, freelancer, or a moderator.
    This permission is checked against a single Dispute object.
    """
    def has_object_permission(self, request, view, obj: Dispute):
        user = request.user
        project = obj.project
        
        is_participant = (user == project.client or user == project.freelancer)
        is_moderator = user.groups.filter(name='Moderators').exists()
        
        return is_participant or is_moderator


class IsDisputeOwner(BasePermission):
    """
    Allows access only to the user who created the dispute.
    """
    def has_object_permission(self, request, view, obj: Dispute):
        return obj.raised_by == request.user

