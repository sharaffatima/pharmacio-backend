from django.db import models
import uuid

# Create your models here.

class Sale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drug_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    quantity_sold = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    sold_at = models.DateTimeField()
