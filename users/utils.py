from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied
from rbac.models import Role
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


def create_admin_user(request_user, username, email, password, first_name='', last_name=''):

    logger.info(f"Attempting to create admin user by: {request_user.username}")

    if not request_user.roles.filter(name='admin').exists():
        logger.warning(
            f"User {request_user.username} does not have admin role")
        raise PermissionDenied("Only admin users can create other admin users")

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        is_staff=True,
    )
    logger.info(f"User {username} created successfully")

    try:
        admin_role = Role.objects.get(name='admin')
        user.roles.add(admin_role)
        logger.info(f"Admin role assigned to {username}")
    except Role.DoesNotExist:
        logger.warning("Admin role not found, creating it")
        admin_role = Role.objects.create(
            name='admin',
            description='Administrator with full system access'
        )
        user.roles.add(admin_role)
        logger.info(f"Admin role created and assigned to {username}")

    return user
