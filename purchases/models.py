from django.db import models
from django.conf import settings

class PurchaseProposal(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name='purchaseproposal_total_cost_non_negative'),
        ]



class PurchaseHistory(models.Model):
    drug_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=255)
    quantity_purchased = models.IntegerField()
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='approved_purchases', null=True, blank=True)

    def __str__(self):
        return f"{self.drug_name} - {self.quantity_purchased} units"
    
    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_purchased__gte=0), name='purchase_quantity_non_negative'),
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name='purchase_total_cost_non_negative'),
        ]
    
