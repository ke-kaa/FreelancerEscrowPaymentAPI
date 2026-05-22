from rest_framework.permissions import BasePermission
from .models import UserProject


class IsClient(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.user_type == 'client'


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.client == request.user


class IsOwnerFreelancer(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.freelancer == request.user
    

class IsFreelancer(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.user_type == 'freelancer'


class IsClientOrAssignedFreelancer(BasePermission):
    """"
    Allows access only to the client or the assigned freelancer of the project.
    Expects the view to have 'project_id' in kwargs.
    """

    def has_permission(self, request, view):
        project_id = view.kwargs.get('project_id')
        if not project_id:
            return False
        try:
            project = UserProject.objects.get(id=project_id)
        except UserProject.DoesNotExist:
            return False
        
        user = request.user
        return project.client == user or project.freelancer == user

        