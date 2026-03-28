import logging

from django.contrib.auth import logout
from django.contrib.auth.hashers import check_password
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from rbac.models import UserRole
from rbac.permissions import user_has_permission
from rbac.services.audit import create_audit_log

from .models import User
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    AdminRegisterSerializer
)

logger = logging.getLogger(__name__)


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
        logger.info("User registration request received")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info(f"User registered successfully: {user.username} ({user.email})")
        
        # Audit log
        create_audit_log(
            actor=user,
            action="user_registered",
            entity=user,
            metadata={'username': user.username, 'email': user.email},
            request=request
        )

        tokens = get_tokens_for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        logger.info("User login request received")
        serializer = LoginSerializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        logger.info(f"User logged in successfully: {user.username}")

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
        logger.info(f"User logout: {request.user.username}")
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
        logger.info(f"Password change request from user: {request.user.username}")
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not check_password(serializer.validated_data['old_password'], user.password):
            logger.warning(f"Failed password change attempt for {request.user.username}: wrong old password")
            return Response({'old_password': 'Wrong password'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        logger.info(f"Password changed successfully for user: {request.user.username}")
        
        # Audit log
        create_audit_log(
            actor=request.user,
            action="password_changed",
            entity=request.user,
            metadata={'username': request.user.username},
            request=request
        )

        tokens = get_tokens_for_user(user)

        return Response({
            'message': 'Password changed successfully',
            'tokens': tokens
        }, status=status.HTTP_200_OK)


class AdminRegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/admin/register/
    """
    queryset = User.objects.all()
    serializer_class = AdminRegisterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logger.info(f"Admin user creation request from: {request.user.username}")
        if not user_has_permission(request.user, 'create_admin'):
            logger.warning(f"User {request.user.username} attempted admin creation without permission")
            return Response({
                'error': 'You do not have permission to create admin users'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info(f"Admin user created successfully by {request.user.username}: {user.username} ({user.email})")
        
        # Audit log
        create_audit_log(
            actor=request.user,
            action="admin_created",
            entity=user,
            metadata={
                'created_by': request.user.username,
                'admin_username': user.username,
                'admin_email': user.email
            },
            request=request
        )
        
        tokens = get_tokens_for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'token': tokens,
            'message': 'Admin user registered successfully'
        }, status=status.HTTP_201_CREATED)
