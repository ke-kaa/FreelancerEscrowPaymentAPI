from django.urls import path

from . import views

urlpatterns = [
    path("", views.EscrowTransactionListView.as_view(), name="escrow-list"),
    path("<int:pk>/", views.EscrowTransactionDetailView.as_view(), name="escrow-detail"),
    path("<int:pk>/release/", views.EscrowReleaseFundsView.as_view(), name="escrow-release"),
    path("<int:pk>/lock/", views.EscrowLockToggleView.as_view(), name="escrow-lock"),
]
