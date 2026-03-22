from django.urls import path

from inventory.views import InventoryListView


urlpatterns = [
    path("inventory", InventoryListView.as_view(), name="inventory-list"),
]
