from django.db import models
import uuid


class Sale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drug_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    quantity_sold = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    sold_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=['drug_name']),
            models.Index(fields=['sold_at']),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_sold__gte=0), name='sale_quantity_non_negative'),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name='sale_unit_price_non_negative'),
        ]