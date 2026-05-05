from django.contrib import admin
from .models import Transaction, TransactionItem, Payment

admin.site.register(Transaction)
admin.site.register(TransactionItem)
admin.site.register(Payment)