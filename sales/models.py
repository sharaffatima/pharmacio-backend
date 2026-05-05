from django.db import models
from django.conf import settings
from inventory.models import Inventory

class Sale(models.Model):
    product_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    quantity_sold = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    sold_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=['product_name']),
            models.Index(fields=['sold_at']),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_sold__gte=0), name='sale_quantity_non_negative'),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name='sale_unit_price_non_negative'),
        ]

class TransactionStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"
    REFUNDED = "refunded", "Refunded"

class Transaction(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="transactions")
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.COMPLETED)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales_transactions"
        indexes = [
            models.Index(fields=["receipt_number"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["cashier"]),
        ]

    def __str__(self):
        return f"Transaction {self.receipt_number}"

class TransactionItem(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="items")
    inventory_item = models.ForeignKey(Inventory, on_delete=models.PROTECT, related_name="transaction_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "sales_transaction_items"
        indexes = [
            models.Index(fields=["transaction"]),
            models.Index(fields=["inventory_item"]),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.inventory_item.product_name}"

class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    INSURANCE = "insurance", "Insurance"

class Payment(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "sales_payments"

    def __str__(self):
        return f"{self.payment_method} - {self.amount_paid}"