from django.db import models
import uuid
# Create your models here.

class Inventory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drug_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    quantity_on_hand = models.IntegerField()
    min_threshold = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.drug_name