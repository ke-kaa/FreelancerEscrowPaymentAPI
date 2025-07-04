from django.shortcuts import render
from rest_framework import views as drf_views, generics, permissions, status
from rest_framework.response import Response


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
    serializer_class = my_serializers.ListProjectSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]    
    queryset = my_models.UserProject.objects.all()


class ListProjectClientAPIView(generics.ListAPIView):
    serializer_class = my_serializers.ListProjectClientSeriailzer
    permission_classes = [permissions.IsAuthenticated, my_permissions.IsClient]
    
    def get_queryset(self):
        return my_models.UserProject.objects.filter(client=self.request.user)