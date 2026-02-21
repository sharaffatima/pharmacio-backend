from django.contrib import admin
from .models import Role, Permission, UserRole, RolePermission
# Register your models here.

admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(UserRole)
admin.site.register(RolePermission)