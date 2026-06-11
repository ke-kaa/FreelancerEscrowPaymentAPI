from django.urls import path

from .views import ChapaWebhookIngressView, StripeWebhookIngressView

urlpatterns = [
    path("stripe/", StripeWebhookIngressView.as_view(), name="webhook-stripe"),
    path("chapa/", ChapaWebhookIngressView.as_view(), name="webhook-chapa"),
]
