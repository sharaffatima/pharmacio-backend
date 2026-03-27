from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def update_postgres_threshold_trigger_for_user_delivery(apps, schema_editor):
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
            created_notification_id bigint;
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
                VALUES (low_message, 'low_stock', NOW())
                RETURNING id INTO created_notification_id;

                INSERT INTO notifications_usernotification (
                    notification_id,
                    user_id,
                    is_read,
                    read_at,
                    created_at,
                    updated_at
                )
                SELECT
                    created_notification_id,
                    u.id,
                    FALSE,
                    NULL,
                    NOW(),
                    NOW()
                FROM users u
                WHERE u.is_active = TRUE
                  AND COALESCE(u.role, '') IN ('admin', 'pharmacist');

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


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_stock_threshold_trigger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserNotification",
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
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "notification",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_notifications",
                        to="notifications.notifications",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="usernotification",
            constraint=models.UniqueConstraint(
                fields=("notification", "user"),
                name="notification_user_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="usernotification",
            index=models.Index(
                fields=["user", "is_read", "created_at"],
                name="notificatio_user_id_6a6c79_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usernotification",
            index=models.Index(
                fields=["notification", "user"],
                name="notificatio_notifi_e7f4cf_idx",
            ),
        ),
        migrations.RunPython(
            update_postgres_threshold_trigger_for_user_delivery,
            reverse_code=noop_reverse,
        ),
    ]
