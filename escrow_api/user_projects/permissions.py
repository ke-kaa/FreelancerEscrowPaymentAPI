from rest_framework.permissions import BasePermission


class IsClient(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.user_type == 'client'


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.client == request.user


class IsFreelancer(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.user_type == 'freelancer'