from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from . import serializers as my_serializers
from user_projects.permissions import IsClientOrAssignedFreelancer, IsOwner
from user_projects.models import UserProject
from .permissions import IsModerator, IsDisputeParticipantOrModerator
from .models import Dispute, DisputeMessage


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


class ListDisputesAPIView(generics.ListAPIView):
    """
    List disputes.
    - Moderators/Admins see all disputes.
    - Clients/Freelancers see only disputes they are involved in.
    """
    serializer_class = my_serializers.DisputeDetailSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['status', 'dispute_type']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.groups.filter(name='Moderators').exists():
            return Dispute.objects.all()
        
        return Dispute.objects.filter(
            Q(project__client=user) | Q(project__freelancer=user)
        )


class RetrieveDisputeAPIView(generics.RetrieveAPIView):
    """
    Retrieve a single dispute's details.
    Accessible only by participants (client, freelancer) or moderators.
    """
    serializer_class = my_serializers.DisputeDetailSerializer
    permission_classes = [IsAuthenticated, IsDisputeParticipantOrModerator]
    authentication_classes = [JWTAuthentication]
    queryset = Dispute.objects.select_related('project', 'raised_by', 'resolved_by')
    lookup_field = 'id'


class ModeratorUpdateDisputeAPIView(generics.UpdateAPIView):
    """
    Allows a moderator to update a dispute (e.g., set status to resolved/closed).
    """
    serializer_class = my_serializers.ModeratorUpdateDisputeSerializer
    permission_classes = [permissions.IsAuthenticated, IsModerator]
    authentication_classes = [JWTAuthentication]
    queryset = Dispute.objects.all()
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        response_serializer = my_serializers.DisputeDetailSerializer(instance)
        return Response(response_serializer.data)

