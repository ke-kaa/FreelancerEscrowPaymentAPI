from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404

from . import serializers as my_serializers
from user_projects.permissions import IsClientOrAssignedFreelancer, IsOwner
from user_projects.models import UserProject

class CreateDisputeAPIView(generics.CreateAPIView):
    """
    Allows an authenticated client or freelancer to create a dispute for a project.
    The URL must contain the project_id.
    """
    serializer_class = my_serializers.CreateDisputeSerializer
    permission_classes = [permissions.IsAuthenticated, IsClientOrAssignedFreelancer, IsOwner]
    authentication_classes = [JWTAuthentication]

    def get_serializer_context(self):
        """
        Pass the project object to the serializer context.if hasattr(project, 'escrotransaction'):
            #     escrow = project.escrotransaction
            #     escrow.is_locked = True
            #     escrow.save(update_fields=['is_locked'])
        The permission class ensures the user has access to this project.
        """
        context = super().get_serializer_context()
        context['project'] = get_object_or_404(UserProject, id=self.kwargs['project_id'])
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response({
            "detail": "Dispute created successfully.",
            "dispute": serializer.data
        }, status=status.HTTP_201_CREATED)

