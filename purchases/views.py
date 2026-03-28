from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_integration.services.comparison import compare_offers
from purchases.models import PurchaseHistory, PurchaseProposal
from purchases.serializers import (
    DrugComparisonSerializer,
    OCRResultIdsSerializer,
    PurchaseProposalSerializer,
    PurchaseProposalStatusSerializer,
)
from purchases.services.proposal_generation import generate_proposal
from rbac.constants import APPROVE_PURCHASE_PROPOSAL
from rbac.permissions import user_has_permission
from rbac.services.audit import create_audit_log


def _get_locked_proposal_or_404(pk):
    return PurchaseProposal.objects.select_for_update().prefetch_related("items").filter(pk=pk).first()


def _require_purchase_proposal_approval_permission(request):
    if user_has_permission(request.user, APPROVE_PURCHASE_PROPOSAL):
        return None
    return Response(
        {"detail": "You do not have permission to approve or reject purchase proposals."},
        status=status.HTTP_403_FORBIDDEN,
    )


class CompareOffersView(APIView):
    """
    POST /api/v1/purchase-proposals/compare
    Body: { "ocr_result_ids": [1, 2, …] }
    Returns: deterministic best-price comparison per drug across the given OCRResult entries.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OCRResultIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ocr_result_ids = serializer.validated_data["ocr_result_ids"]

        comparisons = compare_offers(ocr_result_ids)
        return Response(DrugComparisonSerializer(comparisons, many=True).data)


class GenerateProposalView(APIView):
    """
    POST /api/v1/purchase-proposals/generate
    Body: { "ocr_result_ids": [1, 2, …] }
    Creates a PurchaseProposal with best-priced items (proposed_quantity=1).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OCRResultIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ocr_result_ids = serializer.validated_data["ocr_result_ids"]

        try:
            proposal = generate_proposal(ocr_result_ids, created_by=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        proposal_full = PurchaseProposal.objects.prefetch_related("items").get(pk=proposal.pk)
        return Response(
            PurchaseProposalSerializer(proposal_full).data,
            status=status.HTTP_201_CREATED,
        )


class PurchaseProposalListView(generics.ListAPIView):
    """
    GET /api/v1/purchase-proposals
    Returns all purchase proposals ordered by most recent first.
    """

    queryset = PurchaseProposal.objects.prefetch_related("items").order_by("-created_at")
    serializer_class = PurchaseProposalSerializer
    permission_classes = [IsAuthenticated]


class PurchaseProposalDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/purchase-proposals/:id
    Returns a single purchase proposal with its items.
    """

    queryset = PurchaseProposal.objects.prefetch_related("items")
    serializer_class = PurchaseProposalSerializer
    permission_classes = [IsAuthenticated]


class PurchaseProposalApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        permission_response = _require_purchase_proposal_approval_permission(request)
        if permission_response is not None:
            return permission_response

        with transaction.atomic():
            proposal = _get_locked_proposal_or_404(pk)
            if proposal is None:
                return Response(
                    {"detail": "Purchase proposal not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if proposal.status != "pending":
                return Response(
                    {"detail": f"Only pending proposals can be approved. Current status: {proposal.status}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            proposal.status = "approved"
            proposal.approved_by = request.user
            proposal.save(update_fields=["status", "approved_by", "updated_at"])

            PurchaseHistory.objects.create(
                proposal=proposal,
                total_cost=proposal.total_cost,
                created_by=proposal.created_by,
                approved_by=request.user,
            )

            create_audit_log(
                actor=request.user,
                action="proposal_approved",
                entity=proposal,
                metadata={
                    "proposal_id": proposal.pk,
                    "previous_status": "pending",
                    "new_status": "approved",
                    "total_cost": str(proposal.total_cost),
                },
                request=request,
            )

        return Response(PurchaseProposalSerializer(proposal).data, status=status.HTTP_200_OK)


class PurchaseProposalRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        permission_response = _require_purchase_proposal_approval_permission(request)
        if permission_response is not None:
            return permission_response

        with transaction.atomic():
            proposal = _get_locked_proposal_or_404(pk)
            if proposal is None:
                return Response(
                    {"detail": "Purchase proposal not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if proposal.status != "pending":
                return Response(
                    {"detail": f"Only pending proposals can be rejected. Current status: {proposal.status}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            proposal.status = "rejected"
            proposal.approved_by = request.user
            proposal.save(update_fields=["status", "approved_by", "updated_at"])

            create_audit_log(
                actor=request.user,
                action="proposal_rejected",
                entity=proposal,
                metadata={
                    "proposal_id": proposal.pk,
                    "previous_status": "pending",
                    "new_status": "rejected",
                    "total_cost": str(proposal.total_cost),
                },
                request=request,
            )

        return Response(PurchaseProposalSerializer(proposal).data, status=status.HTTP_200_OK)


class PurchaseProposalStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        proposal = PurchaseProposal.objects.filter(pk=pk).first()
        if proposal is None:
            return Response(
                {"detail": "Purchase proposal not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(PurchaseProposalStatusSerializer(proposal).data, status=status.HTTP_200_OK)

