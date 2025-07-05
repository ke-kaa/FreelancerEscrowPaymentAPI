from django.shortcuts import render
from rest_framework import views as drf_views, generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter, OrderingFilter


from . import serializers as my_serializers, models as my_models
from .permissions import IsClient, IsFreelancer, IsOwner 


class CreateProjectAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.CreateProjectSerializer
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
    queryset = my_models.UserProject.objects.all()


class ListProjectClientAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectClientSerializer
    permission_classes = [IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return my_models.UserProject.objects.filter(client=self.request.user)


class ListProjectFreelancerAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectFreelancerSerializer
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]
    
    def get_queryset(self):
        return my_models.UserProject.objects.filter(is_public=True).filter(freelancer__isnull=True)
    

class RetrieveUpdateDeleteProjectClientAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = my_serializers.RetrieveUpdateDeleteProjectClientSeriailzer
    permission_classes = [IsAuthenticated, IsClient, IsOwner]
    authentication_classes = [JWTAuthentication]
    lookup_field = 'id'

    def get_object(self):
        return get_object_or_404(my_models.UserProject, id=self.kwargs['id'], client=self.request.user)


class RetrieveProjectFreelancerAPIView(generics.RetrieveAPIView):
    serializer_class = my_serializers.RetrieveProjectFreelancerSerializer
    permission_classes = [IsAuthenticated, IsFreelancer]
    authentication_classes = [JWTAuthentication]
    queryset = my_models.UserProject.objects.filter(is_public=True)
    lookup_field = 'id'


class RetrieveProjectAdminAPIView(generics.RetrieveAPIView):
    serializer_class = my_serializers.RetrieveProjectAdminSerializer
    permission_classes = [IsAdminUser, IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset = my_models.UserProject.objects.all()
    lookup_field = 'id'


class CreateProposalAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.CreateProposalSerializer
    permission_classes = [IsFreelancer, IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_poject(self):
        return get_object_or_404(my_models.Proposal, id=self.kwargs['project_id'])
    
    def create(self, request, *args, **kwargs):
        project = self.get_project()

        serializer = self.get_serializer(data=request.data, context={'project': project, 'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project, freelancer=request.user)

        return Response({
            'detail': "Proposal submitted successfully."
        }, status=status.HTTP_201_CREATED)


class ListProjectProposalClientAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectProposalSerializer
    permission_classes = [IsAuthenticated, IsClient]
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['submitted_at']
    ordering = ['-submitted_at']

    def get_project(self):
        return get_object_or_404(my_models.UserProject, id=self.kwargs['project_id'], client=self.request.user)
    
    def get_queryset(self):
        project = self.get_project()
        return my_models.Proposal.objects.filter(project=project, is_withdrawn=False)
    

class RetrieveUpdateProposalClientAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = my_serializers.RetrieveUpdateProposalClientSerializer
    permission_classes = [IsClient, IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    lookup_field = 'id'
    queryset = my_models.Proposal.objects.all()

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


class AcceptProposalClientAPIView(generics.UpdateAPIView):
    serializer_class = my_serializers.AcceptProposalClientSerializer
    permission_classes = [IsClient, IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset = my_models.Proposal.objects.all()
    lookup_field = 'id'
    
    def get_object(self):
        obj = super().get_object()
        if obj.project.client != self.request.user:
            raise PermissionDenied("You are not allowed to accept this proposal.")
        return obj

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            'detail': "Proposal accepted.",
            'proposal_id': instance.id,
            'freelancer': instance.freelancer.get_full_name(),
            'freelancer_email': instance.freelancer.email,
            'project': instance.project.title,
            'status': instance.status,
            'accepted_at': instance.accepted_at,
        }, status=status.HTTP_200_OK)
    

class RejectProposalClientAPIView(generics.UpdateAPIView):
    serializer_class = my_serializers.RejectProposalClientSerializer
    permission_classes = [IsAuthenticated, IsClient]
    queryset = my_models.Proposal.objects.all()
    lookup_field = 'id'

    def get_object(self):
        proposal = super().get_object()
        if proposal.project.client != self.request.user:
            raise PermissionDenied("You do not have permission to reject this proposal.")
        return proposal

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            'detail': "Proposal rejected",
            'proposal_id': instance.id,
            'freelancer': instance.freelancer.get_full_name(),
            'freelancer_email': instance.freelancer.email,
            'project': instance.project.title,
            'status': instance.status,
        }, status=status.HTTP_200_OK)
    

class ListProposalFreelancerAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProposalsFreelancerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsFreelancer, IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ['submitted_at', 'bid_amount', 'estimated_delivery_days',]
    ordering = ['-submitted_at']
    
    def get_queryset(self):
        return my_models.Proposal.objects.filter(freelancer=self.request.user)

