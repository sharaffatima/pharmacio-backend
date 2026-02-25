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
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_purchase_proposals')


    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name='purchaseproposal_total_cost_non_negative'),
        ]

class PurchaseProposalItem(models.Model):
    proposal = models.ForeignKey(PurchaseProposal, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    product_name = models.CharField(max_length=255)
    strength = models.CharField(max_length=100, blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    ware_house_name = models.CharField(max_length=255, null=True, blank=True)
    proposed_quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)



class PurchaseHistory(models.Model):
    proposal = models.ForeignKey(PurchaseProposal, on_delete=models.CASCADE, related_name='purchase_histories', null=True, blank=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    purchased_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='approved_purchases', null=True, blank=True)

    def __str__(self):
        return f"{self.proposal} - {self.total_cost}"
    
    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name='purchase_total_cost_non_negative'),
        ]
    
