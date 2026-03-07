from django.db import models
from files.models import File
import uuid

class OCRJob(models.Model):
    OCRJobStatus = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('dispatched', 'Dispatched'),
        ('ocr_done', 'OCR Done'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    job_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='ocr_jobs')
    status = models.CharField(max_length=50, choices=OCRJobStatus, default='queued')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    retries = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"OCRJob for {self.file.original_filename} - {self.status}" 
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

class OCRResults(models.Model):
    job = models.ForeignKey(OCRJob, null=True, blank=True, on_delete=models.SET_NULL, related_name='ocr_results')
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
    extracted_company = models.CharField(max_length=255, blank=True, null=True)
    extracted_unit_price = models.DecimalField(max_digits=10, decimal_places=2)


