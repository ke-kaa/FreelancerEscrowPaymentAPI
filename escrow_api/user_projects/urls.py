from django.urls import path

from . import views as my_views

urlpatterns = [
    # Project endpoints
    path('client/projects/create/', my_views.CreateProjectClientAPIView.as_view(), name='create-project-client'),
    path('client/projects/list/', my_views.ListProjectClientAPIView.as_view(), name='list-projects-client'),
    path('freelancer/projects/list/', my_views.ListProjectFreelancerAPIView.as_view(), name='list-projects-freelancer'),
    path('admin/projects/list/', my_views.ListProjectAdminAPIView.as_view(), name='list-projects-admin'),

    # Project detail endpoints
    path('client/projects/<int:id>/', my_views.RetrieveUpdateDeleteProjectClientAPIView.as_view(), name='retrieve-update-delete-project-client'),
    path('freelancer/projects/<int:id>/', my_views.RetrieveProjectFreelancerAPIView.as_view(), name='retrieve-project-freelancer'),
    path('admin/projects/<int:id>/', my_views.RetrieveProjectAdminAPIView.as_view(), name='retrieve-project-admin'),

    # Proposal endpoints
    path('client/projects/<int:project_id>/proposals/', my_views.ListProjectProposalsClientAPIView.as_view(), name='list-project-proposals-client'),
    path('freelancer/projects/<int:project_id>/proposal/create/', my_views.CreateProposalFreelancerAPIView.as_view(), name='create-proposal-freelancer'),
    path('freelancer/me/proposals/', my_views.ListProposalFreelancerAPIView.as_view(), name='list-proposals-freelancer'),
    path('admin/projects/<int:project_id>/proposals/', my_views.ListProjectProposalsAdminAPIView.as_view(), name='list-project-proposals-admin'),

    # Proposal detail endpoints
    path('client/proposals/<int:id>/', my_views.RetrieveUpdateProposalClientAPIView.as_view(), name='retrieve-update-proposal-client'),
    path('client/proposals/<int:id>/accept/', my_views.AcceptProposalClientAPIView.as_view(), name='accept-proposal-client'),
    path('client/proposals/<int:id>/reject/', my_views.RejectProposalClientAPIView.as_view(), name='reject-proposal-client'),
    path('freelancer/proposals/<int:id>/', my_views.RetrieveUpdateProposalFreelancerAPIView.as_view(), name='retrieve-update-proposal-freelancer'),
    path('freelancer/proposals/<int:id>/withdraw/', my_views.WithdrawProposalFreelancerAPIView.as_view(), name='withdraw-proposal-freelancer'),
]