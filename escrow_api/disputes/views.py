from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from . import serializers as my_serializers
from user_projects.permissions import IsClientOrAssignedFreelancer, IsOwner
from user_projects.models import UserProject
from .permissions import IsModerator, IsDisputeParticipantOrModerator, IsDisputeOwner
from .models import Dispute, DisputeMessage
from escrow.models import EscrowTransaction


class CreateDisputeAPIView(generics.CreateAPIView):
    """
    Allows an authenticated client or freelancer to create a dispute for a project.
    The URL must contain the project_id.
    """
    serializer_class = my_serializers.DisputeCreateSerializer
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

    @swagger_auto_schema(
        operation_summary="Create a dispute for a project",
        request_body=my_serializers.DisputeCreateSerializer,
        responses={
            201: openapi.Response(description="Dispute created successfully"),
            400: "Validation error"
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

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

    @swagger_auto_schema(
        operation_summary="List disputes with optional filtering",
        manual_parameters=[
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description="Filter disputes by status",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'dispute_type',
                openapi.IN_QUERY,
                description="Filter disputes by dispute type",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'ordering',
                openapi.IN_QUERY,
                description="Order results by one of: created_at, updated_at",
                type=openapi.TYPE_STRING
            ),
        ],
        responses={200: my_serializers.DisputeDetailSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

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

    @swagger_auto_schema(
        operation_summary="Retrieve a dispute",
        responses={200: my_serializers.DisputeDetailSerializer(), 404: "Not found"}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ModeratorUpdateDisputeAPIView(generics.UpdateAPIView):
    """
    Allows a moderator to update a dispute (e.g., set status to resolved/closed).
    """
    serializer_class = my_serializers.ModeratorDisputeUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsModerator]
    authentication_classes = [JWTAuthentication]
    queryset = Dispute.objects.all()
    lookup_field = 'id'

    @swagger_auto_schema(
        operation_summary="Partially update a dispute as moderator",
        request_body=my_serializers.ModeratorDisputeUpdateSerializer,
        responses={200: my_serializers.DisputeDetailSerializer(), 400: "Validation error"}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update a dispute as moderator",
        request_body=my_serializers.ModeratorDisputeUpdateSerializer,
        responses={200: my_serializers.DisputeDetailSerializer(), 400: "Validation error"}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        response_serializer = my_serializers.DisputeDetailSerializer(instance)
        return Response(response_serializer.data)


class UpdateDeleteDisputeAPIView(generics.UpdateDestroyAPIView):
    """
    Allows the user who raised a dispute to update or delete it,
    but only if the dispute is still 'open'.
    """
    serializer_class = my_serializers.UpdateDisputeSerializer
    permission_classes = [IsAuthenticated, IsDisputeOwner]
    authentication_classes = [JWTAuthentication]
    queryset = Dispute.objects.all()
    lookup_field = 'id'

    @swagger_auto_schema(
        operation_summary="Partially update an open dispute",
        request_body=my_serializers.UpdateDisputeSerializer,
        responses={200: my_serializers.UpdateDisputeSerializer(), 400: "Validation error"}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update an open dispute",
        request_body=my_serializers.UpdateDisputeSerializer,
        responses={200: my_serializers.UpdateDisputeSerializer(), 400: "Validation error"}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Delete an open dispute",
        responses={204: "Dispute deleted"}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Custom logic for deleting a dispute.
        """
        if instance.status != 'open':
            raise PermissionDenied("Cannot delete a dispute that is no longer open.")
        
        project = instance.project
        
        with transaction.atomic():
            project.status = 'active'
            project.save(update_fields=['status'])

            escrow = getattr(project, 'escrowtransaction', None)
            if isinstance(escrow, EscrowTransaction):
                updates = []
                if escrow.is_locked:
                    escrow.is_locked = False
                    updates.append('is_locked')
                if escrow.status == 'disputed':
                    escrow.status = 'funded' if escrow.current_balance > 0 else 'pending_funding'
                    updates.append('status')
                if updates:
                    escrow.save(update_fields=updates)
            
            # Finally, delete the dispute instance
            instance.delete()

