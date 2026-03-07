from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rbac.models import Role, Permission
from rbac import constants

User = get_user_model()


class Command(BaseCommand):
    help = "Seed roles and permissions from constants file"

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-password',
            type=str,
            default='admin123',
            help='Password for admin user'
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@example.com',
            help='Email for admin user'
        )

    def handle(self, *args, **options):
        admin_password = options['admin_password']
        admin_email = options['admin_email']

        self.stdout.write(self.style.NOTICE(" Starting RBAC seeding..."))

        self.stdout.write("\n Creating permissions...")

        permission_codes = [
            value for key, value in vars(constants).items()
            if not key.startswith('__') and isinstance(value, str)
        ]

        permissions = {}
        for code in permission_codes:
            perm, created = Permission.objects.get_or_create(
                code=code,
                defaults={'action': code.split('_')[0]}
            )
            permissions[code] = perm
            status = "Created" if created else "Already exists"
            self.stdout.write(f"  {status}: {code}")

        self.stdout.write("\n Creating roles...")

        admin_role, _ = Role.objects.get_or_create(
            name='admin',
            defaults={
                'description': 'System administrator with full access',
                'is_system': True
            }
        )
        admin_role.permissions.set(permissions.values())
        self.stdout.write(" Admin role configured with all permissions")

        pharmacist_role, _ = Role.objects.get_or_create(
            name='pharmacist',
            defaults={
                'description': 'Regular pharmacist with limited access',
                'is_system': True
            }
        )

        pharmacist_permissions = [
            constants.UPLOAD_OFFER_FILES,
        ]

        pharmacist_role.permissions.set(
            [permissions[code]
                for code in pharmacist_permissions if code in permissions]
        )
        self.stdout.write(
            " Pharmacist role configured with limited permissions")

        self.stdout.write("\n Creating admin user...")

        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': admin_email,
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True
            }
        )

        if created:
            admin_user.set_password(admin_password)
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(
                f" Created admin user: admin / {admin_password}"))
        else:
            self.stdout.write(f"Admin user already exists: admin")

        admin_user.roles.add(admin_role)
        self.stdout.write(f" Added Admin role to {admin_user.username}")

        self.stdout.write(self.style.SUCCESS(
            "Seeding completed successfully!"))
