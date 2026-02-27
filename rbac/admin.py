from django.contrib import admin
from .models import AuditLog, Role, Permission, UserRole, RolePermission
# Register your models here.

admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(UserRole)
admin.site.register(RolePermission)
admin.site.register(AuditLog)