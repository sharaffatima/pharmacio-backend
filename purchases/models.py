from django.db import models
import uuid
from django.conf import settings
# Create your models here.

class PurchaseHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drug_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    quantity_purchased = models.IntegerField()
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='approved_purchases', null=True, blank=True)

    def __str__(self):
        return f"{self.drug_name} - {self.quantity_purchased} units"