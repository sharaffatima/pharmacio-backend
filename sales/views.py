from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.models import Inventory
from rbac.constants import RECORD_SALE
from rbac.permissions import user_has_permission
from rbac.services.audit import create_audit_log
from sales.models import Sale
from sales.serializers import SaleCreateSerializer, SaleSerializer


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

		inventory_id = serializer.validated_data["inventory_id"]
		quantity_sold = serializer.validated_data["quantity_sold"]
		unit_price = serializer.validated_data["unit_price"]
		sold_at = serializer.validated_data.get("sold_at", timezone.now())

		with transaction.atomic():
			inventory_item = Inventory.objects.select_for_update().filter(pk=inventory_id).first()
			if inventory_item is None:
				return Response(
					{"detail": "Inventory item not found."},
					status=status.HTTP_404_NOT_FOUND,
				)

			if inventory_item.quantity_on_hand < quantity_sold:
				return Response(
					{
						"detail": (
							f"Insufficient stock for {inventory_item.product_name}. "
							f"Available: {inventory_item.quantity_on_hand}, requested: {quantity_sold}."
						)
					},
					status=status.HTTP_400_BAD_REQUEST,
				)

			previous_quantity = inventory_item.quantity_on_hand
			inventory_item.quantity_on_hand = previous_quantity - quantity_sold
			inventory_item.save(update_fields=["quantity_on_hand", "updated_at"])

			sale = Sale.objects.create(
				product_name=inventory_item.product_name,
				strength=inventory_item.strength,
				quantity_sold=quantity_sold,
				unit_price=unit_price,
				sold_at=sold_at,
			)

			create_audit_log(
				actor=request.user,
				action="sale_recorded",
				entity=sale,
				metadata={
					"inventory_id": inventory_item.pk,
					"product_name": inventory_item.product_name,
					"previous_quantity": previous_quantity,
					"quantity_sold": quantity_sold,
					"remaining_quantity": inventory_item.quantity_on_hand,
					"unit_price": str(unit_price),
				},
				request=request,
			)

		response_data = SaleSerializer(sale).data
		response_data["inventory_id"] = inventory_item.pk
		response_data["remaining_quantity"] = inventory_item.quantity_on_hand
		return Response(response_data, status=status.HTTP_201_CREATED)
