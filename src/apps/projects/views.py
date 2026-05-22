from django.shortcuts import render
from rest_framework import views as drf_views, generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


from . import serializers as my_serializers
from .permissions import IsClient, IsFreelancer, IsOwner, IsClientOrAssignedFreelancer, IsOwnerFreelancer
from .utils import send_proposal_accept_email
from .models import UserProject, Milestone, Review, Proposal
from apps.escrow.services import EscrowService


class CreateProjectClientAPIView(generics.CreateAPIView):
    """Create projects for the authenticated client.

    Methods:
        POST: Create a project owned by the requesting client.

    Request body (required):
        - title (str)
        - description (str)
        - amount (decimal >= 0)

    The request user is attached as ``client`` automatically; no other
    fields are accepted."""
    serializer_class = my_serializers.CreateProjectClientSerializer
    permission_classes = [IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]

    @swagger_auto_schema(
        operation_summary="Create a project (client)",
        request_body=my_serializers.CreateProjectClientSerializer,
        responses={201: openapi.Response(description="Project created", schema=my_serializers.CreateProjectClientSerializer())}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response({
            'detail': "Project created successfully.",
            'project': serializer.data
        }, status=status.HTTP_201_CREATED)
    

class ListProjectAdminAPIView(generics.ListAPIView):
    """List every project for administrators.

    Methods:
        GET: Paginate all projects. No request body required. Supports
        default DRF pagination and ordering query parameters."""
    serializer_class = my_serializers.ListProjectAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]    
    authentication_classes = [JWTAuthentication]
    queryset = UserProject.objects.all()

    @swagger_auto_schema(
        operation_summary="List projects (admin)",
        responses={200: my_serializers.ListProjectAdminSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ListProjectClientAPIView(generics.ListAPIView):
    """List projects owned by the authenticated client.

    Methods:
        GET: Return projects filtered by the requesting client. No body.

    Query params: standard DRF pagination options only."""
    serializer_class = my_serializers.ListProjectClientSerializer
    permission_classes = [IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return UserProject.objects.filter(client=self.request.user)

    @swagger_auto_schema(
        operation_summary="List client projects",
        responses={200: my_serializers.ListProjectClientSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ListProjectFreelancerAPIView(generics.ListAPIView):
    """List public projects available to authenticated freelancers.

    Methods:
        GET: Return public projects without an assigned freelancer. No
        body fields required."""
    serializer_class = my_serializers.ListProjectFreelancerSerializer
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]
    
    def get_queryset(self):
        return UserProject.objects.filter(is_public=True).filter(freelancer__isnull=True)

    @swagger_auto_schema(
        operation_summary="List available projects (freelancer)",
        responses={200: my_serializers.ListProjectFreelancerSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    

class RetrieveUpdateDeleteProjectClientAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Manage a single project owned by the requesting client.

    Methods:
        GET: Retrieve project by ``id`` path parameter.
        PUT/PATCH: Update project details.
        DELETE: Remove project if still pending/eligible.

    Request body for PUT/PATCH (all optional, include only fields to change):
        - title (str)
        - description (str)
        - amount (decimal >= 0)
        - is_public (bool)

    Commission rate, status, and freelancer assignments remain read-only."""
    serializer_class = my_serializers.RetrieveUpdateDeleteProjectClientSerializer
    permission_classes = [IsAuthenticated, IsClient, IsOwner]
    authentication_classes = [JWTAuthentication]
    lookup_field = 'id'

    def get_object(self):
        return get_object_or_404(UserProject, id=self.kwargs['id'], client=self.request.user)

    @swagger_auto_schema(
        operation_summary="Retrieve client project",
        responses={200: my_serializers.RetrieveUpdateDeleteProjectClientSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update client project",
        request_body=my_serializers.RetrieveUpdateDeleteProjectClientSerializer,
        responses={200: my_serializers.RetrieveUpdateDeleteProjectClientSerializer()}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Partially update client project",
        request_body=my_serializers.RetrieveUpdateDeleteProjectClientSerializer,
        responses={200: my_serializers.RetrieveUpdateDeleteProjectClientSerializer()}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Delete client project",
        responses={204: "Project deleted", 400: "Only pending/allowed projects"}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class RetrieveProjectFreelancerAPIView(generics.RetrieveAPIView):
    """Retrieve a public project for a freelancer.

    Methods:
        GET: Fetch project by ``id`` path parameter when the project is
        public and unassigned. No body is accepted."""
    serializer_class = my_serializers.RetrieveProjectFreelancerSerializer
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]
    queryset = UserProject.objects.filter(is_public=True)
    lookup_field = 'id'

    @swagger_auto_schema(
        operation_summary="Retrieve public project (freelancer)",
        responses={200: my_serializers.RetrieveProjectFreelancerSerializer(), 404: "Not found"}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RetrieveProjectAdminAPIView(generics.RetrieveAPIView):
    """Retrieve project information for administrators.

    Methods:
        GET: Fetch project by ``id`` path parameter. No request body."""
    serializer_class = my_serializers.RetrieveProjectAdminSeriailzer
    permission_classes = [IsAdminUser, IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset = UserProject.objects.all()
    lookup_field = 'id'

    @swagger_auto_schema(
        operation_summary="Retrieve project (admin)",
        responses={200: my_serializers.RetrieveProjectAdminSeriailzer(), 404: "Not found"}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CreateProposalFreelancerAPIView(generics.CreateAPIView):
    """Submit a proposal for a specific project as a freelancer.

    Methods:
        POST: Create a proposal tied to ``project_id`` path parameter.

    Request body (required unless noted):
        - cover_letter (str, required)
        - bid_amount (decimal >= 0, required)
        - estimated_delivery_days (int >= 0, required)
        - is_withdrawn (bool, optional; defaults to False)

    The authenticated freelancer is attached automatically."""
    serializer_class = my_serializers.CreateProposalFreelancerSerializer
    permission_classes = [IsFreelancer, IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_project(self):
        return get_object_or_404(UserProject, id=self.kwargs['project_id'])
    
    @swagger_auto_schema(
        operation_summary="Submit proposal (freelancer)",
        request_body=my_serializers.CreateProposalFreelancerSerializer,
        responses={201: openapi.Response(description="Proposal submitted")}
    )
    def create(self, request, *args, **kwargs):
        project = self.get_project()

        serializer = self.get_serializer(data=request.data, context={'project': project, 'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project, freelancer=request.user)

        return Response({
            'detail': "Proposal submitted successfully."
        }, status=status.HTTP_201_CREATED)


class ListProjectProposalsClientAPIView(generics.ListAPIView):
    """List proposals submitted to a client's project.

    Methods:
        GET: Return proposals for ``project_id`` belonging to the
        requesting client. No request body.

    Query params:
        - ordering (optional): ``submitted_at`` for chronological sorting."""
    serializer_class = my_serializers.ListProjectProposalsClientSerializer
    permission_classes = [IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['submitted_at']
    ordering = ['-submitted_at']

    def get_project(self):
        return get_object_or_404(UserProject, id=self.kwargs['project_id'], client=self.request.user)
    
    def get_queryset(self):
        project = self.get_project()
        return Proposal.objects.filter(project=project, is_withdrawn=False)

    @swagger_auto_schema(
        operation_summary="List proposals for a client project",
        manual_parameters=[openapi.Parameter('project_id', openapi.IN_PATH, description="Project ID", type=openapi.TYPE_INTEGER)],
        responses={200: my_serializers.ListProjectProposalsClientSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    

class RetrieveUpdateProposalClientAPIView(generics.RetrieveUpdateAPIView):
    """Inspect or annotate a proposal as the owning client.

    Methods:
        GET: Retrieve proposal by ``id``.
        PATCH/PUT: Update ``client_note`` or mark as seen.

    Request body for PATCH/PUT (all optional):
        - client_note (str)
        - is_seen_by_client (bool)

    Other fields remain read-only to preserve the original submission."""
    serializer_class = my_serializers.RetrieveUpdateProposalClientSerializer
    permission_classes = [IsClient, IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    lookup_field = 'id'
    queryset = Proposal.objects.all()

    def get_object(self):
        proposal = super().get_object()
        if proposal.project.client != self.request.user:
            raise PermissionDenied("You do not have permission to view this proposal.")
        return proposal
    
    @swagger_auto_schema(
        operation_summary="Retrieve proposal (client)",
        responses={200: my_serializers.RetrieveUpdateProposalClientSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        proposal = self.get_object()
        proposal.is_seen_by_client = True
        proposal.save(update_fields=['is_seen_by_client'])
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Partially update proposal (client)",
        request_body=my_serializers.RetrieveUpdateProposalClientSerializer,
        responses={200: my_serializers.RetrieveUpdateProposalClientSerializer()}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update proposal (client)",
        request_body=my_serializers.RetrieveUpdateProposalClientSerializer,
        responses={200: my_serializers.RetrieveUpdateProposalClientSerializer()}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)


class AcceptProposalClientAPIView(drf_views.APIView):
    """Accept a proposal for the client's project.

    Methods:
        POST: Accept proposal identified by ``id`` path parameter.

    Request body: none. The action transitions the proposal to
    ``accepted`` and assigns the freelancer to the project."""
    permission_classes = [IsClient, IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @swagger_auto_schema(
        operation_summary="Accept proposal",
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT, description="No body required"),
        responses={200: openapi.Response(description="Proposal accepted", schema=my_serializers.AcceptProposalClientSerializer()), 400: "Conflict"}
    )
    def post(self, request, id):
        proposal = get_object_or_404(Proposal, id=id)
        if proposal.project.client != request.user:
            raise PermissionDenied("You are not allowed to accept this proposal.")

        if proposal.status == 'accepted':
            return Response({
                    'detail': 'This proposal has already been accepted.'
                }, status=status.HTTP_400_BAD_REQUEST)

        if proposal.project.proposals.filter(status='accepted').exists():
            return Response({
                    'detail': 'A proposal has already been accepted for this project.'
                }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            proposal.status = 'accepted'
            proposal.accepted_at = timezone.now()
            proposal.save(update_fields=['status', 'accepted_at'])

            project = proposal.project
            project.freelancer = proposal.freelancer
            project.status = 'active'
            project.save(update_fields=['freelancer', 'status'])
            project.proposals.exclude(id=proposal.id).update(status='rejected')

            send_proposal_accept_email(proposal.freelancer, proposal)

        serializer = my_serializers.AcceptProposalClientSerializer(proposal)
        return Response({
            'detail': "Proposal accepted.",
            'proposal': serializer.data
        }, status=status.HTTP_200_OK)
    

class RejectProposalClientAPIView(drf_views.APIView):
    """Reject a proposal for the client's project.

    Methods:
        POST: Reject proposal identified by ``id`` path parameter.

    Request body: optional JSON payload (ignored). Proposal status is set
    to ``rejected`` when allowed."""
    serializer_class = my_serializers.RejectProposalClientSerializer
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_summary="Reject proposal",
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT, description="Optional body"),
        responses={200: my_serializers.RejectProposalClientSerializer(), 400: "Invalid state"}
    )
    def post(self, request, id):
        proposal = get_object_or_404(Proposal, id=id)
        if proposal.project.client != request.user:
            raise PermissionDenied("You are not allowed to reject this proposal.")

        if proposal.status == 'accepted':
            return Response({
                    'detail': 'This proposal has already been accepted.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if proposal.status == 'rejected':
            return Response({
                'detail': 'This proposal has already been rejected.'
            }, status=status.HTTP_400_BAD_REQUEST)

        proposal.status = 'rejected'
        proposal.save(update_fields=['status',])

        serializer = my_serializers.RejectProposalClientSerializer(proposal)
        return Response({
            'detail': "Proposal rejected.",
            'status': serializer.data
        }, status=status.HTTP_200_OK)
    

class ListProposalFreelancerAPIView(generics.ListAPIView):
    """List proposals submitted by the authenticated freelancer.

    Methods:
        GET: Return proposals created by the requester. No body allowed.

    Query params:
        - ordering (optional): submitted_at, bid_amount,
          estimated_delivery_days."""
    serializer_class = my_serializers.ListProposalsFreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsFreelancer, IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ['submitted_at', 'bid_amount', 'estimated_delivery_days',]
    ordering = ['-submitted_at']
    
    def get_queryset(self):
        return Proposal.objects.filter(freelancer=self.request.user)

    @swagger_auto_schema(
        operation_summary="List freelancer proposals",
        responses={200: my_serializers.ListProposalsFreelancerSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RetrieveUpdateProposalFreelancerAPIView(generics.RetrieveUpdateAPIView):
    """View or edit a proposal authored by the freelancer.

    Methods:
        GET: Retrieve proposal by ``id``.
        PATCH/PUT: Update editable fields when proposal not accepted.

    Request body for PATCH/PUT (all optional):
        - cover_letter (str)
        - bid_amount (decimal >= 0)
        - estimated_delivery_days (int >= 0)
        - is_withdrawn (bool)

    Immutable fields (status, timestamps) remain read-only."""
    serializer_class = my_serializers.RetrieveUpdateProposalFreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsFreelancer, IsAuthenticated, IsOwnerFreelancer]
    queryset = Proposal.objects.all()
    lookup_field = 'id'

    def get_object(self):
        obj = super().get_object()
        if obj.freelancer != self.request.user:
            raise PermissionDenied("You do not have permission to view this proposal.")

        return obj

    @swagger_auto_schema(
        operation_summary="Retrieve proposal (freelancer)",
        responses={200: my_serializers.RetrieveUpdateProposalFreelancerSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            'detail': "Proposal successfully updated.",
            'proposal': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Update proposal (freelancer)",
        request_body=my_serializers.RetrieveUpdateProposalFreelancerSerializer,
        responses={200: my_serializers.RetrieveUpdateProposalFreelancerSerializer()}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Replace proposal (freelancer)",
        request_body=my_serializers.RetrieveUpdateProposalFreelancerSerializer,
        responses={200: my_serializers.RetrieveUpdateProposalFreelancerSerializer()}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)


class WithdrawProposalFreelancerAPIView(drf_views.APIView):
    """Withdraw a proposal submitted by the authenticated freelancer.

    Methods:
        POST: Withdraw proposal identified by ``id`` path parameter.

    Request body: none. Sets ``is_withdrawn`` to True when proposal is not
    already accepted or withdrawn."""
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]

    @swagger_auto_schema(
        operation_summary="Withdraw proposal",
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT, description="No body required"),
        responses={200: my_serializers.WithdrawProposalFreelancerSerializer(), 400: "Invalid state"}
    )
    def post(self, request, id):
        proposal = get_object_or_404(Proposal, id=id)

        if proposal.freelancer != request.user:
            raise PermissionDenied("You do not have permission to withdraw this proposal.")

        if proposal.is_withdrawn:
            raise ValidationError("This proposal has already been withdrawn.")

        if proposal.status == 'accepted':
            raise ValidationError("You cannot withdraw an accepted proposal.")

        proposal.is_withdrawn = True
        proposal.save(update_fields=['is_withdrawn'])

        seriailzer = my_serializers.WithdrawProposalFreelancerSerializer(proposal)

        return Response(seriailzer.data, status=status.HTTP_200_OK)


class ListProjectProposalsAdminAPIView(generics.ListAPIView):
    """Review proposals on a specific project as an administrator.

    Methods:
        GET: List proposals linked to ``project_id`` path parameter. No
        body fields expected.

    Query params:
        - ordering (optional): submitted_at, updated_at, accepted_at."""
    serializer_class = my_serializers.ListProjectProposalsAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    authentication_classes = [JWTAuthentication]
    filter_backends = [OrderingFilter]
    ordering_fields = ['submitted_at', 'updated_at', 'accepted_at']
    ordering = ['-submitted_at']

    def get_project(self):
        return get_object_or_404(UserProject, id=self.kwargs['project_id'])
    
    def get_queryset(self):
        project = self.get_project()
        return Proposal.objects.filter(project=project)

    @swagger_auto_schema(
        operation_summary="List project proposals (admin)",
        manual_parameters=[openapi.Parameter('project_id', openapi.IN_PATH, description="Project ID", type=openapi.TYPE_INTEGER)],
        responses={200: my_serializers.ListProjectProposalsAdminSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CreateMilestoneClientAPIView(generics.CreateAPIView):
    """Add a milestone to a client's project.

    Methods:
        POST: Create milestone for project specified by ``project_id``.

    Request body (required):
        - title (str)
        - description (str)
        - amount (decimal >= 0)
        - due_date (date in ISO format)

    Only accessible when the requesting client owns the project."""
    serializer_class = my_serializers.CreateMilestoneClientSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]

    def get_project(self):
        return get_object_or_404(UserProject, id=self.kwargs['project_id'], client=self.request.user)
    
    @swagger_auto_schema(
        operation_summary="Create milestone (client)",
        request_body=my_serializers.CreateMilestoneClientSerializer,
        responses={201: openapi.Response(description="Milestone created", schema=my_serializers.CreateMilestoneClientSerializer())}
    )
    def create(self, request, *args, **kwargs):
        project = self.get_project()
        serializer = self.get_serializer(data=request.data, context={'request': request, 'project': project})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response({
            'detail': "Milestone created.",
            'milestone': serializer.data
        }, status=status.HTTP_201_CREATED)
        

class ListProjectMilestonesClientFreelancerAPIView(generics.ListAPIView):
    """List milestones for a project visible to client and freelancer.

    Methods:
        GET: Return milestones for project ``project_id`` when requester
        is the client or assigned freelancer. No body fields."""
    serializer_class = my_serializers.ListProjectMilestonesClientFreelancerSerializer
    permission_classes = [permissions.IsAuthenticated, IsClientOrAssignedFreelancer]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        project = get_object_or_404(UserProject, id=self.kwargs['project_id'])
        user = self.request.user
        if project.client != user and project.freelancer != user:
            raise PermissionDenied("You do not have access to this project's milestones.")
        return Milestone.objects.filter(project=project)

    @swagger_auto_schema(
        operation_summary="List project milestones",
        manual_parameters=[openapi.Parameter('project_id', openapi.IN_PATH, description="Project ID", type=openapi.TYPE_INTEGER)],
        responses={200: my_serializers.ListProjectMilestonesClientFreelancerSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    

class SubmitMilestoneFreelancerAPIView(generics.UpdateAPIView):
    """Submit completed milestone work as the assigned freelancer.

    Methods:
        PATCH: Transition milestone ``id`` from ``pending`` to
        ``submitted``.

    Request body: optional JSON payload (ignored). Status is controlled
    server-side; no fields need to be supplied."""
    serializer_class = my_serializers.SubmitMilestoneFreelancerSerializer
    permission_classes = [permissions.IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]
    queryset = Milestone.objects.all()
    lookup_field = 'id'

    def get_object(self):
        milestone = super().get_object()
        if milestone.project.freelancer != self.request.user:
            raise PermissionDenied("You are not assigned to this milestone.")
        return milestone
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        milestone = my_serializers.MilestoneSummarySeriailzer(instance)
        return Response({
            'detail': "Milestone submitted successfully.",
            'milestone': milestone.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Submit milestone work",
        request_body=my_serializers.SubmitMilestoneFreelancerSerializer,
        responses={200: my_serializers.MilestoneSummarySeriailzer()}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class RetrieveUpdateDeleteMilestoneClientAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Manage a specific milestone as the project client.

    Methods:
        GET: Retrieve milestone by ``id``.
        PATCH/PUT: Update milestone when status is ``pending``.
        DELETE: Remove milestone when status is ``pending``.

    Request body for PATCH/PUT (all optional):
        - title (str)
        - description (str)
        - amount (decimal >= 0)
        - due_date (date ISO)

    Submission timestamps and payment flags remain read-only."""
    serializer_class = my_serializers.RetrieveUpdateDeleteMilestoneClientSerializer
    permission_classes = [IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]
    queryset = Milestone.objects.all()
    lookup_field = 'id'

    def get_object(self):
        milestone = super().get_object()

        if milestone.project.client != self.request.user:
            raise PermissionDenied("You do not have permission to access this milestone.")
        return milestone

    @swagger_auto_schema(
        operation_summary="Retrieve milestone (client)",
        responses={200: my_serializers.RetrieveUpdateDeleteMilestoneClientSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'detail': "Milestone updated successfully.",
            'milestone': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Update milestone (client)",
        request_body=my_serializers.RetrieveUpdateDeleteMilestoneClientSerializer,
        responses={200: my_serializers.RetrieveUpdateDeleteMilestoneClientSerializer()}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Replace milestone (client)",
        request_body=my_serializers.RetrieveUpdateDeleteMilestoneClientSerializer,
        responses={200: my_serializers.RetrieveUpdateDeleteMilestoneClientSerializer()}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.status != 'pending':
            return Response(
                {"detail": "Only pending milestones can be deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.delete()
        return Response({"detail": "Milestone deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_summary="Delete milestone (client)",
        responses={204: "Deleted", 400: "Invalid state"}
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class RetrieveMilestoneFreelancerAPIView(generics.RetrieveAPIView):
    """Retrieve milestone details as the assigned freelancer.

    Methods:
        GET: Fetch milestone by ``id`` when requester is assigned to the
        parent project. No request body."""
    serializer_class = my_serializers.RetrieveMilestoneFreelancerSerializer
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]
    queryset = Milestone.objects.all()
    lookup_field = 'id'

    def get_object(self):
        milestone = super().get_object()
        if milestone.project.freelancer != self.request.user:
            raise PermissionDenied("You do not have permission to view this milestone.")
        return milestone

    @swagger_auto_schema(
        operation_summary="Retrieve milestone (freelancer)",
        responses={200: my_serializers.RetrieveMilestoneFreelancerSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    

class ApproveMilestoneClientAPIView(generics.UpdateAPIView):
    """Approve a submitted milestone and release escrow funds.

    Methods:
        PATCH: Approve milestone ``id`` when status is ``submitted``.

    Request body: optional JSON payload (ignored). Status is updated to
    ``approved`` and escrow release is initiated if the project escrow
    holds enough funds."""
    serializer_class = my_serializers.ApproveMilestoneClientSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]
    queryset = Milestone.objects.all()
    lookup_field = 'id'

    def get_object(self):
        milestone = super().get_object()
        if milestone.project.client != self.request.user:
            raise PermissionDenied("You are not authorized to approve this milestone.")
        return milestone

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        escrow_service = EscrowService()
        release_result = None

        with transaction.atomic():
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            instance.refresh_from_db()
            escrow = getattr(instance.project, 'escrowtransaction', None)
            if not escrow:
                raise ValidationError("Escrow account not found for this project.")
            if escrow.current_balance < instance.amount:
                raise ValidationError("Escrow balance is insufficient for this milestone.")

            release_result = escrow_service.release_funds(
                escrow=escrow,
                amount=instance.amount,
                milestone=instance,
            )

            if release_result.get('status') not in {'pending', 'success'}:
                raise ValidationError(release_result.get('message', 'Unable to release escrow funds'))

        milestone_summary = my_serializers.MilestoneSummarySeriailzer(instance)
        return Response({
            'detail': "Milestone approved successfully. Escrow release initiated.",
            'milestone': milestone_summary.data,
            'payout': release_result,
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Approve milestone (client)",
        request_body=my_serializers.ApproveMilestoneClientSerializer,
        responses={200: my_serializers.MilestoneSummarySeriailzer()}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class RejectMilestoneClientAPIView(generics.UpdateAPIView):
    """Reject a submitted milestone with a required reason.

    Methods:
        PATCH: Reject milestone ``id`` when status is ``submitted``.

    Request body (required):
        - rejected_reason (str)

    The serializer enforces reason presence and sets status to
    ``rejected``."""
    serializer_class = my_serializers.RejectMilestoneClientSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]
    queryset = Milestone.objects.all()
    lookup_field = 'id'

    def get_object(self):
        milestone = super().get_object()
        if milestone.project.client != self.request.user:
            raise PermissionDenied("You are not authorized to reject this milestone.")
        return milestone

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        milestone = my_serializers.MilestoneSummarySeriailzer(instance)
        return Response({
            'detail': "Milestone rejected successfully.",
            'milestone': milestone.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Reject milestone (client)",
        request_body=my_serializers.RejectMilestoneClientSerializer,
        responses={200: my_serializers.MilestoneSummarySeriailzer()}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    

class SubmitReviewAPIView(generics.CreateAPIView):
    """Submit a project review after completion.

    Methods:
        POST: Create a review for project ``project_id`` when requester is
        either the client or assigned freelancer.

    Request body (required unless noted):
        - rating (int, required)
        - communication (int, required)
        - quality (int, required)
        - professionalism (int, required)
        - comment (str, optional)
        - private_comment (str, optional)

    Project, reviewer, reviewee, and review_type are supplied via context
    and cannot be overridden."""
    serializer_class = my_serializers.CreateReviewSerializer
    permission_classes = [IsAuthenticated, IsClientOrAssignedFreelancer]

    def get_project(self):
        return get_object_or_404(UserProject, id=self.kwargs['project_id'])

    def get_review_type(self, project, user):
        if project.client == user:
            return 'client'
        elif project.freelancer == user:
            return 'freelancer'
        raise PermissionDenied("You are not part of this project.")

    def get_reviewee(self, project, user):
        return project.freelancer if user == project.client else project.client

    def get_serializer_context(self):
        project = self.get_project()
        user = self.request.user
        return {
            'request': self.request,
            'project': project,
            'review_type': self.get_review_type(project, user),
            'reviewee': self.get_reviewee(project, user)
        }
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response({
            "detail": "Review submitted successfully.",
            "review": serializer.data
        }, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="Submit project review",
        request_body=my_serializers.CreateReviewSerializer,
        responses={201: my_serializers.CreateReviewSerializer()}
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RetrieveProjectReviewAPIView(generics.RetrieveAPIView):
    """Retrieve a published review for a completed project.

    Methods:
        GET: Fetch review by ``id`` when the review is visible and the
        project is completed. No request body."""
    serializer_class = my_serializers.RetrieveProjectReviewSerializer
    permission_classes = [IsAuthenticated]
    queryset = Review.objects.all()
    lookup_field = 'id'

    def get_object(self):
        review = super().get_object()
        project = review.project

        if project.status != 'completed' or not review.is_visible:
            raise PermissionDenied("Review is not available.")
        
        return review

    @swagger_auto_schema(
        operation_summary="Retrieve project review",
        responses={200: my_serializers.RetrieveProjectReviewSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    

class UpdateReviewAPIView(generics.RetrieveUpdateAPIView):
    """Edit a review within the permitted update window.

    Methods:
        GET: Retrieve review by ``id`` when requester is the reviewer.
        PATCH/PUT: Update review details before the update deadline.

    Request body for PATCH/PUT (all optional, include at least one field):
        - rating (int)
        - communication (int)
        - quality (int)
        - professionalism (int)
        - comment (str)
        - private_comment (str)

    Server validates the update window using
    ``REVIEW_UPDATE_WINDOW_DAYS``."""
    queryset = Review.objects.all()
    serializer_class = my_serializers.UpdateProjectReviewSerializer
    permission_classes = [IsAuthenticated, IsClientOrAssignedFreelancer]

    def get_object(self):
        review = super().get_object()
        if review.reviewer != self.request.user:
            raise PermissionDenied("You do not have permission to update this review.")
        return review

    @swagger_auto_schema(
        operation_summary="Update project review",
        request_body=my_serializers.UpdateProjectReviewSerializer,
        responses={200: my_serializers.UpdateProjectReviewSerializer()}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Replace project review",
        request_body=my_serializers.UpdateProjectReviewSerializer,
        responses={200: my_serializers.UpdateProjectReviewSerializer()}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

