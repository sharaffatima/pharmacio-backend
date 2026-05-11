from django.db import models

class Inventory(models.Model):
    product_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    quantity_on_hand = models.IntegerField()
    min_threshold = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name
    
    class Meta:
        indexes = [
            models.Index(fields=['product_name']),
            models.Index(fields=['strength']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_on_hand__gte=0),
                name="quantity_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(min_threshold__gte=0),
                name="min_threshold_non_negative"
            ),
            models.UniqueConstraint(
                fields=['product_name', 'strength'],
                name='inventory_product_strength_unique'
            ),
        ]


class InventoryBarcode(models.Model):
    inventory_item = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name="barcodes",
    )
    barcode = models.CharField(max_length=128, unique=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.barcode

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(barcode=""),
                name="inventory_barcode_not_blank",
            ),
        ]
