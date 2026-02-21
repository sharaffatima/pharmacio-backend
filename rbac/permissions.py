from rest_framework import permissions
from .models import UserRole


def user_has_permission(user, permission_code):
    if not user or not user.is_authenticated:
        return False

    if UserRole.objects.filter(user=user, role__name='admin').exists():
        return True

    user_roles = UserRole.objects.filter(user=user).select_related(
        'role').prefetch_related('role__permissions')
    for user_role in user_roles:
        for perm in user_role.role.permissions.all():
            if perm.code == permission_code:
                return True

    return False


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return user_has_permission(request.user, '') 


class HasPermission(permissions.BasePermission):

    def __init__(self, permission_code):
        self.permission_code = permission_code

    def has_permission(self, request, view):
        return user_has_permission(request.user, self.permission_code)
