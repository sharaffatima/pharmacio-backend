from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from rbac.models import Role


class User(AbstractUser):
    
    role = models.CharField(
        _('role'),
        max_length=50, 
        default='pharmacist', 
        help_text=_('User role for permission management'),
        blank=True,  
        null=True,   
    )

    phone_number = models.CharField(
        _('phone number'),
        max_length=15,
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Designates whether this user should be treated as active.')
    )

    date_joined = models.DateTimeField(
        _('date joined'),
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )

    roles = models.ManyToManyField(
        'rbac.Role',
        through='rbac.UserRole',
        through_fields=('user', 'role'),
        related_name='users'
    )

    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"{self.username} ({self.role or 'No Role'})"


    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_pharmacist(self):
        return self.role == 'pharmacist'
