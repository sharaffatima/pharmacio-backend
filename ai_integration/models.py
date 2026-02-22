from django.db import models
import uuid

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

    class Meta:
        indexes = [
            models.Index(fields=['drug_name']),
            models.Index(fields=['company']),
            models.Index(fields=['created_at']),
            models.Index(fields=['review_required']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(confidence__gte=0) & models.Q(confidence__lte=1)),
                name='ocr_confidence_range'
            ),
        ]
