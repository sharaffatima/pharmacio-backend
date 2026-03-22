from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="inventory",
            constraint=models.CheckConstraint(
                condition=models.Q(min_threshold__gte=0),
                name="min_threshold_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventory",
            constraint=models.UniqueConstraint(
                fields=("product_name", "strength"),
                name="inventory_product_strength_unique",
            ),
        ),
    ]
