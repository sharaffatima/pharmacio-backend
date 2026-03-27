from django.urls import path

from purchases.views import (
    CompareOffersView,
    GenerateProposalView,
    PurchaseProposalApproveView,
    PurchaseProposalDetailView,
    PurchaseProposalListView,
    PurchaseProposalRejectView,
    PurchaseProposalStatusView,
)

urlpatterns = [
    path("purchase-proposals/compare", CompareOffersView.as_view(), name="purchase-proposals-compare-no-slash"),
    path("purchase-proposals/compare/", CompareOffersView.as_view(), name="purchase-proposals-compare"),
    path("purchase-proposals/generate", GenerateProposalView.as_view(), name="purchase-proposals-generate-no-slash"),
    path("purchase-proposals/generate/", GenerateProposalView.as_view(), name="purchase-proposals-generate"),
    path("purchase-proposals/<int:pk>/approve", PurchaseProposalApproveView.as_view(), name="purchase-proposal-approve-no-slash"),
    path("purchase-proposals/<int:pk>/approve/", PurchaseProposalApproveView.as_view(), name="purchase-proposal-approve"),
    path("purchase-proposals/<int:pk>/reject", PurchaseProposalRejectView.as_view(), name="purchase-proposal-reject-no-slash"),
    path("purchase-proposals/<int:pk>/reject/", PurchaseProposalRejectView.as_view(), name="purchase-proposal-reject"),
    path("purchase-proposals/<int:pk>/status", PurchaseProposalStatusView.as_view(), name="purchase-proposal-status-no-slash"),
    path("purchase-proposals/<int:pk>/status/", PurchaseProposalStatusView.as_view(), name="purchase-proposal-status"),
    path("purchase-proposals/<int:pk>", PurchaseProposalDetailView.as_view(), name="purchase-proposal-detail-no-slash"),
    path("purchase-proposals/<int:pk>/", PurchaseProposalDetailView.as_view(), name="purchase-proposal-detail"),
    path("purchase-proposals", PurchaseProposalListView.as_view(), name="purchase-proposals-list-no-slash"),
    path("purchase-proposals/", PurchaseProposalListView.as_view(), name="purchase-proposals-list"),
]
