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


class InventoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = ["product_name", "strength", "quantity_on_hand", "min_threshold"]

    def validate(self, attrs):
        if Inventory.objects.filter(
            product_name=attrs["product_name"],
            strength=attrs["strength"],
        ).exists():
            raise serializers.ValidationError(
                "An inventory item with this product name and strength already exists."
            )
        return attrs

    def validate_quantity_on_hand(self, value):
        if value < 0:
            raise serializers.ValidationError("quantity_on_hand cannot be negative.")
        return value

    def validate_min_threshold(self, value):
        if value < 0:
            raise serializers.ValidationError("min_threshold cannot be negative.")
        return value


class InventoryAdjustSerializer(serializers.Serializer):
    """
    Accepts a signed integer delta (positive = restock, negative = write-off)
    and an optional human-readable reason for the audit log.
    """
    adjustment = serializers.IntegerField(
        help_text="Signed quantity delta (positive or negative)."
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
    )
