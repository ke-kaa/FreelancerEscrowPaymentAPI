from django.shortcuts import render
from rest_framework import views as drf_views, generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from . import serializers as my_serializers, permissions as my_permissions, models as my_models


class CreateProjectAPIView(generics.CreateAPIView):
    serializer_class = my_serializers.CreateProjectSerializer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsClient]

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
    queryset = my_models.UserProject.objects.all()


class ListProjectClientAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectClientSerializer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsClient]
    
    def get_queryset(self):
        return my_models.UserProject.objects.filter(client=self.request.user)


class ListProjectFreelancerAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectFreelancerSerializer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsFreelancer]
    
    def get_queryset(self):
        return my_models.UserProject.objects.filter(is_public=True)
    

class RetrieveUpdateDeleteProjectClientAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = my_serializers.RetrieveUpdateDeleteProjectClientSeriailzer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsClient, my_permissions.IsOwner]
    lookup_field = 'id'

    def get_object(self):
        return get_object_or_404(my_models.UserProject, id=self.kwargs['id'], client=self.request.user)