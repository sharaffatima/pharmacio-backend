from django.urls import path

from sales.views import (
    SaleCreateView,
    POSCheckoutView,
    TransactionListView,
    TransactionReceiptView,
    POSRefundView
)


urlpatterns = [
    # Legacy endpoint
    path("sales/", SaleCreateView.as_view(), name="sales-create"),
    
    # New POS Endpoints
    path("sales/checkout/", POSCheckoutView.as_view(), name="pos-checkout"),
    path("sales/transactions/", TransactionListView.as_view(), name="pos-transactions"),
    path("sales/transactions/<int:transaction_id>/receipt/", TransactionReceiptView.as_view(), name="pos-receipt"),
    path("sales/transactions/<int:transaction_id>/refund/", POSRefundView.as_view(), name="pos-refund"),
]
