from rest_framework import serializers
from .models import Role, Permission, UserRole, RolePermission
from users.models import User
from users.serializers import UserSerializer


class PermissionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Permission
        fields = ['id', 'code', 'action']
        read_only_fields = ['id']
class RoleSerializer(serializers.ModelSerializer):

    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'is_system',
                  'permissions', 'permission_ids', 'users_count',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'is_system', 'created_at', 'updated_at']

    def get_users_count(self, obj):
        return obj.user_roles.count()

    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        role = Role.objects.create(**validated_data)

        for perm_id in permission_ids:
            RolePermission.objects.get_or_create(
                role=role,
                permission_id=perm_id
            )
        return role

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if permission_ids is not None:
            instance.role_permissions.all().delete()
            for perm_id in permission_ids:
                RolePermission.objects.get_or_create(
                    role=instance,
                    permission_id=perm_id
                )
        return instance


class RolePermissionAssignmentSerializer(serializers.Serializer):

    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )

    def validate_permission_ids(self, value):
        existing = Permission.objects.filter(id__in=value).count()
        if existing != len(value):
            raise serializers.ValidationError(
                "One or more permission IDs are invalid")
        return value


class UserRoleAssignmentSerializer(serializers.Serializer):

    role_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )

    def validate_role_ids(self, value):
        existing = Role.objects.filter(id__in=value).count()
        if existing != len(value):
            raise serializers.ValidationError(
                "One or more role IDs are invalid")
        return value


class UserWithRolesSerializer(serializers.ModelSerializer):

    roles = serializers.SerializerMethodField()  
    role_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'phone_number', 'is_active', 'roles', 'role_ids']
        read_only_fields = ['id']

    def get_roles(self, obj):

        from .models import UserRole
        user_roles = UserRole.objects.filter(user=obj).select_related('role')
        return [{
            'id': ur.role.id,
            'name': ur.role.name,
            'description': ur.role.description,
            'is_system': ur.role.is_system,
        } for ur in user_roles]
