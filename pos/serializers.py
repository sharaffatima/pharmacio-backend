from rest_framework import serializers

from inventory.models import InventoryBarcode
from pos.models import Transaction, TransactionItem, Payment


class TransactionItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="inventory_item.product_name", read_only=True)
    strength = serializers.CharField(source="inventory_item.strength", read_only=True)
    
    class Meta:
        model = TransactionItem
        fields = ["id", "inventory_item", "product_name", "strength", "quantity", "unit_price", "discount_percentage", "total_price"]

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "payment_method", "amount_paid"]

class TransactionSerializer(serializers.ModelSerializer):
    items = TransactionItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source="cashier.username", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "receipt_number", "cashier", "cashier_name", "status", 
            "discount_percentage", "subtotal", "total_amount", 
            "created_at", "updated_at", "items", "payments"
        ]

# Input serializer for Checkout
class CheckoutItemInputSerializer(serializers.Serializer):
    inventory_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=0.00, min_value=0, max_value=100)

class CheckoutPaymentInputSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=["cash", "card", "insurance"])
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)

class CheckoutInputSerializer(serializers.Serializer):
    items = CheckoutItemInputSerializer(many=True, allow_empty=False)
    payments = CheckoutPaymentInputSerializer(many=True, allow_empty=False)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=0.00, min_value=0, max_value=100)


class BarcodeLookupSerializer(serializers.ModelSerializer):
    inventory_id = serializers.IntegerField(source="inventory_item_id", read_only=True)
    product_name = serializers.CharField(source="inventory_item.product_name", read_only=True)
    strength = serializers.CharField(source="inventory_item.strength", read_only=True)
    quantity_on_hand = serializers.IntegerField(source="inventory_item.quantity_on_hand", read_only=True)
    min_threshold = serializers.IntegerField(source="inventory_item.min_threshold", read_only=True)

    class Meta:
        model = InventoryBarcode
        fields = [
            "barcode",
            "inventory_id",
            "product_name",
            "strength",
            "quantity_on_hand",
            "min_threshold",
        ]
