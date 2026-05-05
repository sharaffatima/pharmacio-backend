from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError as DRFValidationError

from rbac.constants import RECORD_SALE
from rbac.permissions import user_has_permission
from sales.models import Sale, Transaction
from sales.serializers import (
    SaleCreateSerializer, 
    SaleSerializer,
    TransactionSerializer,
    CheckoutInputSerializer
)
from sales.services import POSService
from django.shortcuts import get_object_or_404


# Keep old view for backwards compatibility
class SaleCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_has_permission(request.user, RECORD_SALE):
            return Response(
                {"detail": "You do not have permission to record sales."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SaleCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Backward compatibility layer using the new POS Service
        # To not duplicate logic, we could call checkout here, but we will leave 
        # it simple or raise deprecation warning
        return Response({"detail": "Please use the new POS checkout endpoint: /api/sales/checkout/"}, status=status.HTTP_400_BAD_REQUEST)


class POSCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_has_permission(request.user, RECORD_SALE):
            return Response(
                {"detail": "You do not have permission to record sales."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CheckoutInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = POSService.checkout(
                user=request.user,
                items_data=serializer.validated_data['items'],
                payments_data=serializer.validated_data['payments'],
                transaction_discount_percentage=serializer.validated_data.get('discount_percentage', 0)
            )
            return Response(TransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)
        except DRFValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"Checkout failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transactions = Transaction.objects.all().order_by('-created_at')[:100]
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TransactionReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        serializer = TransactionSerializer(transaction)
        return Response(serializer.data, status=status.HTTP_200_OK)


class POSRefundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):
        if not user_has_permission(request.user, RECORD_SALE):
            return Response(
                {"detail": "You do not have permission to refund sales."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            transaction = POSService.refund(user=request.user, transaction_id=transaction_id)
            return Response(TransactionSerializer(transaction).data, status=status.HTTP_200_OK)
        except DRFValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"Refund failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
