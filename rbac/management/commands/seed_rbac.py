from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rbac.services.audit import create_audit_log
from rbac.models import Role, Permission, UserRole

User = get_user_model()


class Command(BaseCommand):
    help = "Seed simple roles: Admin and Pharmacist only"

    def handle(self, *args, **options):


        perm, created = Permission.objects.get_or_create(
            code='create_admin',
            defaults={
                'action': 'create',
            }
        )
        if created:
            self.stdout.write(f"  Created permission: {perm.code}")
        else:
            self.stdout.write(f"  Permission already exists: {perm.code}")

        self.stdout.write("\nCreating roles...")

        admin_role, created = Role.objects.get_or_create(
            name='admin',
            defaults={
                'description': 'System administrator',
                'is_system': True
            }
        )
        if created:
            self.stdout.write("   Created Admin role")
            admin_role.permissions.add(perm)
            self.stdout.write(
                f"     Added {perm.code} permission to Admin role")
            
            # Log role creation in audit log
            create_audit_log(
                actor=None,
                action="create_role",
                entity=admin_role,
                metadata={"source": "seed_rbac"},
    )
        else:
            self.stdout.write("   Admin role already exists")
            if perm not in admin_role.permissions.all():
                admin_role.permissions.add(perm)
                self.stdout.write(
                    f"     Added missing {perm.code} permission to Admin role")

        pharmacist_role, created = Role.objects.get_or_create(
            name='pharmacist',
            defaults={
                'description': 'Regular pharmacist',
                'is_system': True
            }
        )
        if created:
            self.stdout.write("   Created Pharmacist role (no permissions)")
            
            # Log role creation in audit log
            create_audit_log(
                actor=None,
                action="create_role",
                entity=pharmacist_role,
                metadata={"source": "seed_rbac"},)

        else:
            self.stdout.write("   Pharmacist role already exists")

        self.stdout.write("\nCreating default admin user...")

        default_username = 'admin'
        default_email = 'admin@example.com'
        default_password = 'admin123'

        admin_user = User.objects.filter(username=default_username).first()

        if not admin_user:
            admin_user = User.objects.create_user(
                username=default_username,
                email=default_email,
                password=default_password,
                first_name='Admin',
                last_name='User',
                is_staff=True,
                is_superuser=True
            )
            self.stdout.write(self.style.SUCCESS(
                f"   Created default admin user: {default_username} / {default_password}"))
            
            # Log admin_user creation in audit log
            admin_user.roles.add(admin_user)
            create_audit_log(
                actor=None,
                action="created_admin_user",
                entity=admin_user,
                metadata={"admin_user_name": admin_user.name, "source": "seed_rbac"},
            )



        else:
            self.stdout.write(
                f"   Admin user already exists: {default_username}")

        if not UserRole.objects.filter(user=admin_user, role=admin_role).exists():
            UserRole.objects.create(
                user=admin_user,
                role=admin_role,
                assigned_by=admin_user
            )
            self.stdout.write(
                f"   Assigned Admin role to {admin_user.username}")
        
            admin_user.roles.add(admin_role)
            create_audit_log(
                actor=None,
                action="assign_role",
                entity=admin_user,
                metadata={"role": admin_role.name, "source": "seed_rbac"},
                )

        else:
            self.stdout.write(
                f"   {admin_user.username} already has Admin role")

        self.stdout.write(self.style.SUCCESS(
            "\n Seeding completed successfully!"))
