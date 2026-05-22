from django.urls import path

from . import views

urlpatterns = [
    path(
        'projects/<int:project_id>/disputes/',
        views.CreateDisputeAPIView.as_view(),
        name='project-disputes-create',
    ),
    path(
        'disputes/',
        views.ListDisputesAPIView.as_view(),
        name='disputes-list',
    ),
    path(
        'disputes/<int:id>/',
        views.RetrieveDisputeAPIView.as_view(),
        name='disputes-detail',
    ),
    path(
        'disputes/<int:id>/moderator/',
        views.ModeratorUpdateDisputeAPIView.as_view(),
        name='disputes-moderator-update',
    ),
    path(
        'disputes/<int:id>/owner/',
        views.UpdateDeleteDisputeAPIView.as_view(),
        name='disputes-owner-update-delete',
    ),
]
