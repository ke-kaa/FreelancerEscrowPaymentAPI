from django.urls import path
from .views import (
    InitiateFundingView,
    VerifyFundingView,
    ReleaseFundsView,
    RefundView,
    EscrowDetailView,
    EscrowPaymentsView,
    PayoutMethodListCreateView,
    PayoutMethodDetailView,
    ChapaBanksView,
    StripeOnboardingLinkView,
    StripeWebhookView,
    ChapaWebhookView,
)

urlpatterns = [
    path('funding/initiate/<int:project_id>/', InitiateFundingView.as_view()),
    path('funding/verify/', VerifyFundingView.as_view()),
    path('release/', ReleaseFundsView.as_view()),
    path('refund/', RefundView.as_view()),
    path('escrow/<int:escrow_id>/', EscrowDetailView.as_view()),
    path('escrow/<int:escrow_id>/payments/', EscrowPaymentsView.as_view()),

    path('payout-methods/', PayoutMethodListCreateView.as_view()),
    path('payout-methods/<int:method_id>/', PayoutMethodDetailView.as_view()),

    path('providers/chapa/banks/', ChapaBanksView.as_view()),
    path('providers/stripe/onboarding-link/', StripeOnboardingLinkView.as_view()),

    # webhooks
    path('webhooks/stripe/', StripeWebhookView.as_view()),
    path('webhooks/chapa/', ChapaWebhookView.as_view()),
]

