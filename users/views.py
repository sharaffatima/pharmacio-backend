from rbac.models import UserRole, Role, Permission
from rbac.permissions import user_has_permission
from rbac.models import Role
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied
from rbac.models import RolePermission, Permission
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import check_password
from rbac.permissions import HasPermission
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    AdminRegisterSerializer
)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class RegisterView(generics.CreateAPIView):

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        tokens = get_tokens_for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        tokens = get_tokens_for_user(user)

        user_roles = UserRole.objects.filter(user=user).select_related('role')
        roles_data = []
        permissions_data = set()

        for user_role in user_roles:
            role = user_role.role
            roles_data.append({
                'id': role.id,
                'name': role.name,
                'description': role.description,
                'is_system': role.is_system,
            })

            for permission in role.permissions.all():
                permissions_data.add(permission.code)

        return Response({
            'user': UserSerializer(user).data,
            'roles': roles_data,
            'permissions': list(permissions_data),
            'token': tokens,
            'message': 'Login successful'
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not check_password(serializer.validated_data['old_password'], user.password):
            return Response({'old_password': 'Wrong password'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        tokens = get_tokens_for_user(user)

        return Response({
            'message': 'Password changed successfully',
            'tokens': tokens
        }, status=status.HTTP_200_OK)


class AdminRegisterView(generics.CreateAPIView):
    """
    POST /api/auth/admin/register/
    """
    queryset = User.objects.all()
    serializer_class = AdminRegisterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not user_has_permission(request.user, 'create_admin'):
            return Response({
                'error': 'You do not have permission to create admin users'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = get_tokens_for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'token': tokens,
            'message': 'Admin user registered successfully'
        }, status=status.HTTP_201_CREATED)
