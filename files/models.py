import uuid
from django.db import models


class File(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    s3_key = models.CharField(max_length=255, unique=True)
    original_filename = models.CharField(max_length=255)
    ware_house_name = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename

    class Meta:
        indexes = [
            models.Index(fields=['s3_key']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
