from django.urls import path

from pos.views import (
    POSCheckoutView,
    TransactionListView,
    TransactionReceiptView,
    POSRefundView
)

urlpatterns = [
    path("pos/checkout/", POSCheckoutView.as_view(), name="pos-checkout"),
    path("pos/transactions/", TransactionListView.as_view(), name="pos-transactions"),
    path("pos/transactions/<int:transaction_id>/receipt/", TransactionReceiptView.as_view(), name="pos-receipt"),
    path("pos/transactions/<int:transaction_id>/refund/", POSRefundView.as_view(), name="pos-refund"),
]
