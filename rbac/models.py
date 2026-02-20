from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Permission(models.Model):

    ACTION_TYPES = (
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    )

    code = models.CharField(
        _('codename'),
        max_length=100,
        unique=True,
        help_text=_(
            'Unique permission code (e.g., create_user, view_inventory)')
    )

    action = models.CharField(
        _('action'),
        max_length=20,
        choices=ACTION_TYPES,
        default='read'
    )

 

    class Meta:
        db_table = 'rbac_permissions'
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return self.code


class Role(models.Model):

    name = models.CharField(_('name'), max_length=50, unique=True)
    description = models.TextField(_('description'), blank=True)
    permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('permissions'),
        blank=True,
        related_name='roles',
        through='RolePermission'
    )
    is_system = models.BooleanField(
        _('system role'),
        default=False,
        help_text=_('System roles cannot be deleted')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        db_table = 'rbac_roles'
        verbose_name = _('role')
        verbose_name_plural = _('roles')

    def __str__(self):
        return self.name

class Role(models.Model):

    name = models.CharField(_('name'), max_length=50, unique=True)
    description = models.TextField(_('description'), blank=True)
    permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('permissions'),
        blank=True,
        related_name='roles',
        through='RolePermission'
    )
    is_system = models.BooleanField(
        _('system role'),
        default=False,
        help_text=_('System roles cannot be deleted')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        db_table = 'rbac_roles'
        verbose_name = _('role')
        verbose_name_plural = _('roles')

    def __str__(self):
        return self.name


class RolePermission(models.Model):

    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rbac_role_permissions'
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role.name} - {self.permission.code}"


class UserRole(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='role_assignments'
    )
    assigned_at = models.DateTimeField(_('assigned at'), auto_now_add=True)

    class Meta:
        db_table = 'rbac_user_roles'
        verbose_name = _('user role')
        verbose_name_plural = _('user roles')
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"
