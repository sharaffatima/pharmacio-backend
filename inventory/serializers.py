from rest_framework import serializers

from inventory.models import Inventory


class InventoryListSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source="product_name")
    quantity = serializers.IntegerField(source="quantity_on_hand")
    status = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = ["product", "quantity", "status"]

    def get_status(self, obj):
        return "low" if obj.quantity_on_hand <= obj.min_threshold else "ok"
