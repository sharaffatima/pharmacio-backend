from django.core.management.base import BaseCommand
from inventory.models import Inventory

class Command(BaseCommand):
    help = "Seed inventory with demo data"

    def handle(self, *args, **options):
        demo_data = [
            {
                'product_name': 'Aspirin',
                'strength': '500mg',
                'quantity_on_hand': 100,
                'min_threshold': 20
            },
            {
                'product_name': 'Paracetamol',
                'strength': '500mg',
                'quantity_on_hand': 150,
                'min_threshold': 30
            },
            {
                'product_name': 'Ibuprofen',
                'strength': '200mg',
                'quantity_on_hand': 80,
                'min_threshold': 15
            },
        ]

        for item in demo_data:
            inventory_item, created = Inventory.objects.get_or_create(
                product_name=item['product_name'],
                strength=item['strength'],
                defaults={
                    'quantity_on_hand': item['quantity_on_hand'],
                    'min_threshold': item['min_threshold']
                }
            )
            if created:
                self.stdout.write(f"Created inventory item: {inventory_item}")
            else:
                self.stdout.write(f"Inventory item already exists: {inventory_item}")