from django.db import models
import uuid
import files
# Create your models here.

class OCRResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drug_name = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    price = models.CharField(max_length=255)
    availability = models.CharField(max_length=255)
    confidence = models.FloatField()
    review_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OCRResult for {self.drug_name} by {self.company}"
