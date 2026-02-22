from django.test import TestCase

# Create your tests here.
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from rbac.models import Role, Permission, UserRole, RolePermission


class RBACApiTests(APITestCase):

    API_PREFIX = "/api/rbac"

    def setUp(self):
        User = get_user_model()
        self.User = User

        # Create users
        self.admin_user = User.objects.create_user(
            username="admin1",
            email="admin@example.com",
            password="pass1234",
        )
        self.normal_user = User.objects.create_user(
            username="user1",
            email="user@example.com",
            password="pass1234",
        )

        
        self.admin_user.role = "admin"
        self.admin_user.save(update_fields=["role"])
        self.normal_user.role = "pharmacist"
        self.normal_user.save(update_fields=["role"])

        # Create roles in RBAC tables
        self.admin_role = Role.objects.create(
            name="admin",
            description="System admin role",
            is_system=True,
        )
        self.pharmacist_role = Role.objects.create(
            name="pharmacist",
            description="Default pharmacist role",
            is_system=True,
        )

        
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)


    def test_non_admin_cannot_create_permission(self):
        """POST /permissions/ should be forbidden for non-admin."""
        self.client.force_authenticate(user=self.normal_user)

        url = f"{self.API_PREFIX}/permissions/"
        payload = {"code": "inventory.read", "action": "read"}

        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_permission(self):
        """POST /permissions/ should succeed for admin."""
        self.client.force_authenticate(user=self.admin_user)

        url = f"{self.API_PREFIX}/permissions/"
        payload = {"code": "inventory.read", "action": "read"}

        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Permission.objects.filter(code="inventory.read").exists())

    def test_admin_can_assign_permissions_to_role(self):
        """POST /roles/{role_id}/permissions/ assigns permissions to a role."""
        # Create a permission first
        perm = Permission.objects.create(code="inventory.update", action="update")

        # Create a role to assign to (non-system, just to test)
        role = Role.objects.create(name="inventory_manager", description="Manages inventory")

        self.client.force_authenticate(user=self.admin_user)

        url = f"{self.API_PREFIX}/roles/{role.id}/permissions/"
        payload = {"permission_ids": [perm.id]}

        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertTrue(
            RolePermission.objects.filter(role=role, permission=perm).exists()
        )

    def test_admin_can_assign_roles_to_user(self):
        """POST /users/{user_id}/roles/ assigns roles to a user."""
        self.client.force_authenticate(user=self.admin_user)

        # Assign pharmacist_role to normal_user
        url = f"{self.API_PREFIX}/users/{self.normal_user.id}/roles/"
        payload = {"role_ids": [self.pharmacist_role.id]}

        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertTrue(
            UserRole.objects.filter(user=self.normal_user, role=self.pharmacist_role).exists()
        )

    def test_check_permission_returns_true_when_user_has_permission(self):
        """
        GET /check-permission/?code=... returns has_permission=true
        when user's roles grant that permission.
        """
        # Create permission and role, link them
        perm = Permission.objects.create(code="offers.upload", action="create")
        role = Role.objects.create(name="uploader", description="Can upload offers")
        RolePermission.objects.create(role=role, permission=perm)

        # Assign role to normal_user
        UserRole.objects.create(user=self.normal_user, role=role)

        self.client.force_authenticate(user=self.normal_user)

        url = f"{self.API_PREFIX}/check-permission/?code=offers.upload"
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("has_permission", res.data)
        self.assertTrue(res.data["has_permission"])

    def test_check_permission_returns_false_when_missing(self):
        """GET /check-permission/?code=... returns false if user lacks it."""
        self.client.force_authenticate(user=self.normal_user)

        url = f"{self.API_PREFIX}/check-permission/?code=does.not.exist"
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["has_permission"])