from django.db import models
from files.models import File

class OCRResults(models.Model):
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='ocr_results')
    ware_house_name = models.CharField(max_length=255, null=True, blank=True)
    confidence_score = models.FloatField()
    review_required = models.BooleanField(default=False)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OCRResults for {self.ware_house_name}"

    class Meta:
        indexes = [
            models.Index(fields=['ware_house_name']),
            models.Index(fields=['file']),
            models.Index(fields=['created_at']),
            models.Index(fields=['review_required']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(confidence_score__gte=0) & models.Q(confidence_score__lte=1)),
                name='ocr_confidence_range'
            ),
        ]

class OCRResultItem(models.Model):
    ocr_result = models.ForeignKey(OCRResults, on_delete=models.CASCADE, related_name='items')
    extracted_product_name = models.CharField(max_length=255)
    extracted_strength = models.CharField(max_length=100, blank=True, null=True)
    extracted_company = models.CharField(max_length=255, blank=True, null=True)
    extracted_quantity = models.PositiveIntegerField()
    extracted_unit_price = models.DecimalField(max_digits=10, decimal_places=2)
