from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response

from .models import EscrowTransaction
from .serializers import (
	EscrowLockSerializer,
	EscrowReleaseSerializer,
	EscrowTransactionSerializer,
)
from .services import EscrowService


class EscrowTransactionListView(generics.ListAPIView):
	"""List all escrows relevant to the authenticated user."""

	serializer_class = EscrowTransactionSerializer
	permission_classes = [permissions.IsAuthenticated]

	def get_queryset(self):
		user = self.request.user
		queryset = EscrowTransaction.objects.select_related(
			"project",
			"project__client",
			"project__freelancer",
		).prefetch_related("payments")

		if user.is_staff:
			return queryset

		user_type = getattr(user, "user_type", None)
		if user_type == "client":
			return queryset.filter(project__client=user)
		if user_type == "freelancer":
			return queryset.filter(project__freelancer=user)
		return queryset.none()


class EscrowTransactionDetailView(generics.RetrieveAPIView):
	serializer_class = EscrowTransactionSerializer
	permission_classes = [permissions.IsAuthenticated]
	queryset = EscrowTransaction.objects.select_related(
		"project",
		"project__client",
		"project__freelancer",
	).prefetch_related("payments")

	def check_object_permissions(self, request, obj):
		super().check_object_permissions(request, obj)
		if request.user.is_staff:
			return
		user_type = getattr(request.user, "user_type", None)
		if user_type == "client" and obj.project.client_id == request.user.id:
			return
		if user_type == "freelancer" and obj.project.freelancer_id == request.user.id:
			return
		self.permission_denied(request, message="Not authorised to access this escrow.")


class EscrowReleaseFundsView(views.APIView):
	permission_classes = [permissions.IsAuthenticated]

	def post(self, request, pk):
		escrow = get_object_or_404(
			EscrowTransaction.objects.select_related("project", "project__client", "project__freelancer"),
			pk=pk,
		)

		if escrow.project.client_id != request.user.id and not request.user.is_staff:
			return Response(
				{"detail": "Only the project client can release escrow funds."},
				status=status.HTTP_403_FORBIDDEN,
			)

		serializer = EscrowReleaseSerializer(data=request.data, context={"escrow": escrow})
		serializer.is_valid(raise_exception=True)

		service = EscrowService()
		result = service.release_funds(escrow=escrow, amount=serializer.validated_data["amount"])

		http_status = status.HTTP_200_OK if result.get("status") == "success" else status.HTTP_400_BAD_REQUEST
		return Response(result, status=http_status)

