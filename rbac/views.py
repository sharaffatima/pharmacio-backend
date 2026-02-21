from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Role, Permission, UserRole, RolePermission
from users.models import User
from .serializers import (
    RoleSerializer, PermissionSerializer,
    RolePermissionAssignmentSerializer, UserRoleAssignmentSerializer,
    UserWithRolesSerializer
)
from .permissions import IsAdminUser, HasPermission



class PermissionListView(generics.ListCreateAPIView):
    """
    GET /api/rbac/permissions/
    POST /api/rbac/permissions/
    """
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data.get('code')
        if Permission.objects.filter(code=code).exists():
            return Response({
                'error': f'Permission with code "{code}" already exists'
            }, status=status.HTTP_400_BAD_REQUEST)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response({
            'message': 'Permission created successfully',
            'permission': serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

class PermissionDetailView(generics.RetrieveAPIView):
    """
    GET /api/rbac/permissions/{id}/
    """
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]



class RoleListView(generics.ListCreateAPIView):
    """
    GET /api/rbac/roles/
    POST /api/rbac/roles/
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def perform_create(self, serializer):
        serializer.save()


class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /api/rbac/roles/{id}/
    PUT /api/rbac/roles/{id}/
    DELETE /api/rbac/roles/{id}/
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def perform_destroy(self, instance):
        if instance.is_system:
            raise PermissionError("Cannot delete system role")
        instance.delete()



class RolePermissionsView(APIView):
    """
    GET /api/rbac/roles/{role_id}/permissions/
    POST /api/rbac/roles/{role_id}/permissions/
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request, role_id):
        role = get_object_or_404(Role, id=role_id)
        permissions = role.permissions.all()
        serializer = PermissionSerializer(permissions, many=True)
        return Response(serializer.data)

    def post(self, request, role_id):
        role = get_object_or_404(Role, id=role_id)
        serializer = RolePermissionAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        permission_ids = serializer.validated_data['permission_ids']

        RolePermission.objects.filter(role=role).delete()

        for perm_id in permission_ids:
            RolePermission.objects.get_or_create(
                role=role,
                permission_id=perm_id
            )

        return Response({
            'message': 'Permissions assigned successfully',
            'permissions': PermissionSerializer(role.permissions.all(), many=True).data
        }, status=status.HTTP_200_OK)



class UserRolesView(APIView):
    """
    GET /api/rbac/users/{user_id}/roles/
    POST /api/rbac/users/{user_id}/roles/
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = UserWithRolesSerializer(user)
        return Response(serializer.data)

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = UserRoleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role_ids = serializer.validated_data['role_ids']

        UserRole.objects.filter(user=user).delete()

        for role_id in role_ids:
            UserRole.objects.get_or_create(
                user=user,
                role_id=role_id,
                defaults={'assigned_by': request.user}
            )

        if role_ids:
            admin_role = Role.objects.filter(name='admin').first()
            if admin_role and admin_role.id in role_ids:
                user.role = 'admin'
            else:
                user.role = 'pharmacist'
            user.save()

        return Response({
            'message': 'Roles assigned successfully',
            'user': UserWithRolesSerializer(user).data
        }, status=status.HTTP_200_OK)


class UserRemoveRoleView(APIView):
    """
    DELETE /api/rbac/users/{user_id}/roles/{role_id}/
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def delete(self, request, user_id, role_id):
        user = get_object_or_404(User, id=user_id)
        role = get_object_or_404(Role, id=role_id)

        deleted, _ = UserRole.objects.filter(user=user, role=role).delete()

        if deleted:
            return Response({
                'message': f'Role {role.name} removed from user {user.username}'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'User does not have this role'
            }, status=status.HTTP_404_NOT_FOUND)



class CheckPermissionView(APIView):
    """
    GET /api/rbac/check-permission/?code=permission_code
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        permission_code = request.query_params.get('code')
        if not permission_code:
            return Response({'error': 'Permission code required'}, status=400)

        if request.user.is_admin:
            has_perm = True
        else:
            user_permissions = set()
            for role in request.user.roles.all():
                for perm in role.permissions.all():
                    user_permissions.add(perm.code)
            has_perm = permission_code in user_permissions

        return Response({
            'permission': permission_code,
            'has_permission': has_perm
        })
