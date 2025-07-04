from django.shortcuts import render
from rest_framework import views as drf_views, generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework_simplejwt import authentication
from django.shortcuts import get_object_or_404


from . import serializers as my_serializers, permissions as my_permissions, models as my_models


class CreateProjectAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.CreateProjectSerializer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsClient]
    authentication_classes = [authentication.JWTAuthentication]

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
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]    
    authentication_classes = [authentication.JWTAuthentication]
    queryset = my_models.UserProject.objects.all()


class ListProjectClientAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectClientSerializer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsClient]
    authentication_classes = [authentication.JWTAuthentication]

    def get_queryset(self):
        return my_models.UserProject.objects.filter(client=self.request.user)


class ListProjectFreelancerAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectFreelancerSerializer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsFreelancer]
    authentication_classes = [authentication.JWTAuthentication]
    
    def get_queryset(self):
        return my_models.UserProject.objects.filter(is_public=True).filter(freelancer__isnull=True)
    

class RetrieveUpdateDeleteProjectClientAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = my_serializers.RetrieveUpdateDeleteProjectClientSeriailzer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsClient, my_permissions.IsOwner]
    authentication_classes = [authentication.JWTAuthentication]
    lookup_field = 'id'

    def get_object(self):
        return get_object_or_404(my_models.UserProject, id=self.kwargs['id'], client=self.request.user)


class CreateProposalAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.CreateProposalSerializer
    permission_classes = [my_permissions.IsFreelancer, permissions.IsAuthenticated]
    authentication_classes = [authentication.JWTAuthentication]

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
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsClient]
    authentication_classes = [authentication.JWTAuthentication]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['submitted_at']
    ordering = ['-submitted_at']

    def get_project(self):
        return get_object_or_404(my_models.UserProject, id=self.kwargs['project_id'], client=self.request.user)
    
    def get_queryset(self):
        project = self.get_project()
        return my_models.Proposal.objects.filter(project=project, is_withdrawn=False)
        