from rest_framework import serializers

from sales.models import Sale


class SaleCreateSerializer(serializers.Serializer):
    inventory_id = serializers.IntegerField()
    quantity_sold = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    sold_at = serializers.DateTimeField(required=False)


class SaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = [
            "id",
            "product_name",
            "strength",
            "quantity_sold",
            "unit_price",
            "sold_at",
        ]
