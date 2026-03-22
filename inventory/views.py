from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.models import Inventory
from inventory.serializers import (
    InventoryAdjustSerializer,
    InventoryCreateSerializer,
    InventoryListSerializer,
)
from rbac.constants import ADJUST_INVENTORY, CREATE_INVENTORY
from rbac.permissions import user_has_permission
from rbac.services.audit import create_audit_log


class InventoryListCreateView(generics.ListCreateAPIView):
    queryset = Inventory.objects.all().order_by("product_name", "id")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return InventoryCreateSerializer
        return InventoryListSerializer

    def create(self, request, *args, **kwargs):
        if not user_has_permission(request.user, CREATE_INVENTORY):
            return Response(
                {"detail": "You do not have permission to create inventory items."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            item = serializer.save()
            create_audit_log(
                actor=request.user,
                action="inventory_item_created",
                entity=item,
                metadata={
                    "product_name": item.product_name,
                    "strength": item.strength,
                    "quantity_on_hand": item.quantity_on_hand,
                    "min_threshold": item.min_threshold,
                },
                request=request,
            )
        return Response(
            InventoryListSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class InventoryAdjustView(APIView):
    """
    POST /api/v1/inventory/<pk>/adjust
    Applies a signed quantity delta to a single inventory item.
    Requires the `adjust_inventory` permission.
    Writes an audit log entry on every successful adjustment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not user_has_permission(request.user, ADJUST_INVENTORY):
            return Response(
                {"detail": "You do not have permission to adjust inventory."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InventoryAdjustSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        adjustment = serializer.validated_data["adjustment"]
        reason = serializer.validated_data["reason"]

        with transaction.atomic():
            try:
                item = Inventory.objects.select_for_update().get(pk=pk)
            except Inventory.DoesNotExist:
                return Response(
                    {"detail": "Inventory item not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            new_quantity = item.quantity_on_hand + adjustment
            if new_quantity < 0:
                return Response(
                    {
                        "detail": (
                            f"Adjustment would result in negative stock "
                            f"({item.quantity_on_hand} + {adjustment} = {new_quantity})."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            previous_quantity = item.quantity_on_hand
            item.quantity_on_hand = new_quantity
            item.save(update_fields=["quantity_on_hand"])

            create_audit_log(
                actor=request.user,
                action="inventory_adjusted",
                entity=item,
                metadata={
                    "product_name": item.product_name,
                    "previous_quantity": previous_quantity,
                    "adjustment": adjustment,
                    "new_quantity": new_quantity,
                    "reason": reason,
                },
                request=request,
            )

        return Response(
            {
                "id": item.pk,
                "product": item.product_name,
                "previous_quantity": previous_quantity,
                "adjustment": adjustment,
                "quantity": new_quantity,
            },
            status=status.HTTP_200_OK,
        )
