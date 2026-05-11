from django.contrib import admin
from .models import Inventory, InventoryBarcode

# Register your models here.

admin.site.register(Inventory)
admin.site.register(InventoryBarcode)
