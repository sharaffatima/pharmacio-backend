from django.db import migrations, models
import django.db.models.deletion


def create_postgres_threshold_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        """
        CREATE OR REPLACE FUNCTION notifications_handle_inventory_threshold()
        RETURNS trigger AS $$
        DECLARE
            record_id bigint;
            was_low boolean;
            is_low boolean;
            low_message text;
            recovered_message text;
        BEGIN
            is_low := NEW.quantity_on_hand <= NEW.min_threshold;

            SELECT id, is_below_threshold
            INTO record_id, was_low
            FROM notifications_stockalertrecord
            WHERE inventory_id = NEW.id
            FOR UPDATE;

            IF NOT FOUND THEN
                INSERT INTO notifications_stockalertrecord (
                    inventory_id,
                    is_below_threshold,
                    last_notified_at,
                    last_notified_quantity,
                    updated_at
                )
                VALUES (NEW.id, FALSE, NULL, NULL, NOW())
                RETURNING id, is_below_threshold INTO record_id, was_low;
            END IF;

            IF is_low AND NOT was_low THEN
                low_message := format(
                    'Low stock alert: %%s (%%s) is at %%s, threshold is %%s.',
                    NEW.product_name,
                    NEW.strength,
                    NEW.quantity_on_hand,
                    NEW.min_threshold
                );

                INSERT INTO notifications_notifications (message, type, created_at)
                VALUES (low_message, 'low_stock', NOW());

                INSERT INTO notifications_notificationlog (
                    inventory_id,
                    record_id,
                    event,
                    message,
                    created_notifications,
                    created_at
                )
                VALUES (
                    NEW.id,
                    record_id,
                    'low_stock_detected',
                    low_message,
                    1,
                    NOW()
                );

                UPDATE notifications_stockalertrecord
                SET
                    is_below_threshold = TRUE,
                    last_notified_at = NOW(),
                    last_notified_quantity = NEW.quantity_on_hand,
                    updated_at = NOW()
                WHERE id = record_id;

            ELSIF NOT is_low AND was_low THEN
                recovered_message := format(
                    'Stock recovered: %%s (%%s) is now %%s, threshold is %%s.',
                    NEW.product_name,
                    NEW.strength,
                    NEW.quantity_on_hand,
                    NEW.min_threshold
                );

                INSERT INTO notifications_notificationlog (
                    inventory_id,
                    record_id,
                    event,
                    message,
                    created_notifications,
                    created_at
                )
                VALUES (
                    NEW.id,
                    record_id,
                    'stock_recovered',
                    recovered_message,
                    0,
                    NOW()
                );

                UPDATE notifications_stockalertrecord
                SET
                    is_below_threshold = FALSE,
                    updated_at = NOW()
                WHERE id = record_id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_inventory_threshold_notify ON inventory_inventory;

        CREATE TRIGGER trg_inventory_threshold_notify
        AFTER INSERT OR UPDATE OF quantity_on_hand, min_threshold
        ON inventory_inventory
        FOR EACH ROW
        EXECUTE FUNCTION notifications_handle_inventory_threshold();
        """
    )


def drop_postgres_threshold_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        """
        DROP TRIGGER IF EXISTS trg_inventory_threshold_notify ON inventory_inventory;
        DROP FUNCTION IF EXISTS notifications_handle_inventory_threshold();
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_inventory_hardening_constraints"),
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockAlertRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("is_below_threshold", models.BooleanField(default=False)),
                ("last_notified_at", models.DateTimeField(blank=True, null=True)),
                ("last_notified_quantity", models.IntegerField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "inventory",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_alert_record",
                        to="inventory.inventory",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["is_below_threshold"],
                        name="notificatio_is_belo_452656_idx",
                    ),
                    models.Index(
                        fields=["updated_at"],
                        name="notificatio_updated_adb2a8_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="NotificationLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event",
                    models.CharField(
                        choices=[
                            ("low_stock_detected", "Low Stock Detected"),
                            ("stock_recovered", "Stock Recovered"),
                        ],
                        max_length=64,
                    ),
                ),
                ("message", models.TextField()),
                ("created_notifications", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "inventory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_logs",
                        to="inventory.inventory",
                    ),
                ),
                (
                    "record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="notifications.stockalertrecord",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["event", "created_at"],
                        name="notificatio_event_270401_idx",
                    ),
                    models.Index(
                        fields=["inventory", "created_at"],
                        name="notificatio_invento_085f2d_idx",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            create_postgres_threshold_trigger,
            reverse_code=drop_postgres_threshold_trigger,
        ),
    ]
