from django.contrib import admin
from .models import PurchaseHistory, PurchaseProposal, PurchaseProposalItem
# Register your models here.

admin.site.register(PurchaseHistory)
admin.site.register(PurchaseProposal)
admin.site.register(PurchaseProposalItem)