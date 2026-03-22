from rest_framework import generics

from inventory.models import Inventory
from inventory.serializers import InventoryListSerializer


class InventoryListView(generics.ListAPIView):
    queryset = Inventory.objects.all().order_by("product_name", "id")
    serializer_class = InventoryListSerializer
