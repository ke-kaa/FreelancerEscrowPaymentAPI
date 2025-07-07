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


from . import serializers as my_serializers
from .permissions import IsClient, IsFreelancer, IsOwner, IsClientOrAssignedFreelancer
from .utils import send_proposal_accept_email
from .models import UserProject, Milestone, Review, Proposal


class CreateProjectClientAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.CreateProjectClientSerializer
    permission_classes = [IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response({
            'detail': "Project created successfully.",
            'project': serializer.data
        }, status=status.HTTP_201_CREATED)
    

class ListProjectAdminAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]    
    authentication_classes = [JWTAuthentication]
    queryset = UserProject.objects.all()


class ListProjectClientAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectClientSerializer
    permission_classes = [IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return UserProject.objects.filter(client=self.request.user)


class ListProjectFreelancerAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectFreelancerSerializer
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]
    
    def get_queryset(self):
        return UserProject.objects.filter(is_public=True).filter(freelancer__isnull=True)
    

class RetrieveUpdateDeleteProjectClientAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = my_serializers.RetrieveUpdateDeleteProjectClientSeriailzer
    permission_classes = [IsAuthenticated, IsClient, IsOwner]
    authentication_classes = [JWTAuthentication]
    lookup_field = 'id'

    def get_object(self):
        return get_object_or_404(UserProject, id=self.kwargs['id'], client=self.request.user)


class RetrieveProjectFreelancerAPIView(generics.RetrieveAPIView):
    serializer_class = my_serializers.RetrieveProjectFreelancerSerializer
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]
    queryset = UserProject.objects.filter(is_public=True)
    lookup_field = 'id'


class RetrieveProjectAdminAPIView(generics.RetrieveAPIView):
    serializer_class = my_serializers.RetrieveProjectAdminSerializer
    permission_classes = [IsAdminUser, IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset = UserProject.objects.all()
    lookup_field = 'id'


class CreateProposalFreelancerAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.CreateProposalFreelancerSerializer
    permission_classes = [IsFreelancer, IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_project(self):
        return get_object_or_404(UserProject, id=self.kwargs['project_id'])
    
    def create(self, request, *args, **kwargs):
        project = self.get_project()

        serializer = self.get_serializer(data=request.data, context={'project': project, 'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project, freelancer=request.user)

        return Response({
            'detail': "Proposal submitted successfully."
        }, status=status.HTTP_201_CREATED)


class ListProjectProposalsClientAPIView(generics.ListAPIView):
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
    

class RetrieveUpdateProposalClientAPIView(generics.RetrieveUpdateAPIView):
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
    
    def partial_update(self, request, *args, **kwargs):
        proposal = self.get_object()
        proposal.is_seen_by_client = True
        proposal.save(updated_fields=['is_seen_by_client'])
        return super().partial_update(request, *args, **kwargs)


class AcceptProposalClientAPIView(drf_views.APIView):
    permission_classes = [IsClient, IsAuthenticated]
    authentication_classes = [JWTAuthentication]

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
    serializer_class = my_serializers.RejectProposalClientSerializer
    permission_classes = [IsAuthenticated, IsClient]

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
    serializer_class = my_serializers.ListProposalsFreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsFreelancer, IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ['submitted_at', 'bid_amount', 'estimated_delivery_days',]
    ordering = ['-submitted_at']
    
    def get_queryset(self):
        return Proposal.objects.filter(freelancer=self.request.user)


class RetrieveUpdateProposalFreelancerAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = my_serializers.RetrieveUpdateProposalFreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsFreelancer, IsAuthenticated, IsOwner]
    queryset = Proposal.objects.all()
    lookup_field = 'id'

    def get_object(self):
        obj = super().get_object()
        if obj.freelancer != self.request.user:
            raise PermissionDenied("You do not have permission to view this proposal.")

        return obj
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            'detail': "Proposal successfully updated.",
            'proposal': serializer.data
        }, status=status.HTTP_200_OK)


class WithdrawProposalFreelancerAPIView(drf_views.APIView):
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]

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


class CreateMilestoneClientAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.CreateMilestoneClientSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]

    def get_project(self):
        return get_object_or_404(UserProject, id=self.kwargs['project_id'], client=self.request.user)
    
    def create(self, request, *args, **kwargs):
        project = self.get_project()
        serializer = self.get_serializer(data=request.data, context={'request': request, 'project': project})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response({
            'detail': "Milestone created.",
            'milestone': serializer.data
        }, status=status.HTTP_201_CREATED)
        

class ListProjectMilestonesAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectMilestoneSerializer
    permission_classes = [permissions.IsAuthenticated, IsClientOrAssignedFreelancer]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        project = get_object_or_404(UserProject, id=self.kwargs['project_id'])
        user = self.request.user
        if project.client != user and project.freelancer != user:
            raise PermissionDenied("You do not have access to this project's milestones.")
        return Milestone.objects.filter(project=project)
    
