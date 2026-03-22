from django.urls import path

from inventory.views import InventoryAdjustView, InventoryListCreateView


urlpatterns = [
    path("inventory", InventoryListCreateView.as_view(), name="inventory-list"),
    path("inventory/<int:pk>/adjust", InventoryAdjustView.as_view(), name="inventory-adjust"),
]
