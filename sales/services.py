from decimal import Decimal
import uuid
from datetime import datetime

from django.db import transaction
from rest_framework.exceptions import ValidationError

from inventory.models import Inventory
from sales.models import Transaction, TransactionItem, Payment, TransactionStatus
from rbac.models import AuditLog


class POSService:
    
    @staticmethod
    def _generate_receipt_number():
        date_str = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4().hex)[:6].upper()
        return f"TXN-{date_str}-{unique_id}"

    @staticmethod
    @transaction.atomic
    def checkout(user, items_data, payments_data, transaction_discount_percentage=Decimal('0.00')):
        if not items_data:
            raise ValidationError("At least one item is required for checkout.")
        if not payments_data:
            raise ValidationError("Payment details are required.")

        # 1. Initialize Transaction
        pos_txn = Transaction.objects.create(
            receipt_number=POSService._generate_receipt_number(),
            cashier=user,
            status=TransactionStatus.COMPLETED,
            discount_percentage=transaction_discount_percentage,
            subtotal=Decimal('0.00'),
            total_amount=Decimal('0.00'),
        )

        subtotal = Decimal('0.00')

        # 2. Process Items and Inventory
        transaction_items = []
        for item_data in items_data:
            inventory_id = item_data['inventory_id']
            quantity = item_data['quantity']
            unit_price = item_data['unit_price']
            item_discount_percentage = item_data.get('discount_percentage', Decimal('0.00'))

            try:
                inventory = Inventory.objects.select_for_update().get(id=inventory_id)
            except Inventory.DoesNotExist:
                raise ValidationError(f"Inventory item with ID {inventory_id} not found.")

            if inventory.quantity_on_hand < quantity:
                raise ValidationError(f"Insufficient stock for {inventory.product_name}. Available: {inventory.quantity_on_hand}")

            # Calculate price for this item
            item_gross_price = unit_price * quantity
            discount_amount = item_gross_price * (item_discount_percentage / Decimal('100.00'))
            item_total_price = item_gross_price - discount_amount

            transaction_items.append(TransactionItem(
                transaction=pos_txn,
                inventory_item=inventory,
                quantity=quantity,
                unit_price=unit_price,
                discount_percentage=item_discount_percentage,
                total_price=item_total_price
            ))

            # Deduct inventory
            inventory.quantity_on_hand -= quantity
            inventory.save(update_fields=['quantity_on_hand', 'updated_at'])

            subtotal += item_gross_price

        # Bulk create items
        TransactionItem.objects.bulk_create(transaction_items)

        # 3. Process Payments
        total_paid = Decimal('0.00')
        payments = []
        for payment_data in payments_data:
            amount_paid = payment_data['amount_paid']
            payments.append(Payment(
                transaction=pos_txn,
                payment_method=payment_data['payment_method'],
                amount_paid=amount_paid
            ))
            total_paid += amount_paid

        Payment.objects.bulk_create(payments)

        # 4. Finalize totals
        txn_discount_amount = subtotal * (transaction_discount_percentage / Decimal('100.00'))
        total_amount = subtotal - txn_discount_amount

        # Allow slight rounding differences or overpayments (e.g. change for cash)
        # Assuming exact match or overpayment is fine, but we'll enforce >= total_amount
        if total_paid < total_amount:
            raise ValidationError(f"Insufficient payment. Total is {total_amount}, but only {total_paid} provided.")

        pos_txn.subtotal = subtotal
        pos_txn.total_amount = total_amount
        pos_txn.save(update_fields=['subtotal', 'total_amount', 'updated_at'])

        # 5. Log action for Dashboard
        AuditLog.objects.create(
            actor=user,
            action="sale_recorded",
            resource="Transaction",
            resource_id=str(pos_txn.id),
            details={"receipt_number": pos_txn.receipt_number, "total": str(total_amount)}
        )

        return pos_txn

    @staticmethod
    @transaction.atomic
    def refund(user, transaction_id):
        try:
            pos_txn = Transaction.objects.select_for_update().get(id=transaction_id)
        except Transaction.DoesNotExist:
            raise ValidationError("Transaction not found.")

        if pos_txn.status == TransactionStatus.REFUNDED:
            raise ValidationError("Transaction is already refunded.")

        # Return items to inventory
        for item in pos_txn.items.all():
            inventory = Inventory.objects.select_for_update().get(id=item.inventory_item_id)
            inventory.quantity_on_hand += item.quantity
            inventory.save(update_fields=['quantity_on_hand', 'updated_at'])

        pos_txn.status = TransactionStatus.REFUNDED
        pos_txn.save(update_fields=['status', 'updated_at'])

        # Log action for Dashboard
        AuditLog.objects.create(
            actor=user,
            action="refund_processed",
            resource="Transaction",
            resource_id=str(pos_txn.id),
            details={"receipt_number": pos_txn.receipt_number, "total": str(pos_txn.total_amount)}
        )

        return pos_txn
