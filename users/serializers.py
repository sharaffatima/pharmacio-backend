from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User
from rest_framework.exceptions import PermissionDenied
from rbac.models import Role
from .utils import create_admin_user


from rbac.models import UserRole, Role


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'roles', 'phone_number', 'is_active', 'date_joined')
        read_only_fields = ('id', 'date_joined')

    def get_roles(self, obj):
        user_roles = UserRole.objects.filter(user=obj).select_related('role')
        return [ur.role.name for ur in user_roles]

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email',
            'password', 'password2',
            'first_name', 'last_name',
            'phone_number'
        ]

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError(
                {"password": "Passwords don't match"})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')

        user = User.objects.create_user(**validated_data, password=password)

        try:
            pharmacist_role = Role.objects.get(name='pharmacist')
            user.roles.add(pharmacist_role)
        except Role.DoesNotExist:
    
            pass

        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )
            if not user:
                msg = 'Unable to log in with provided credentials.'
                raise serializers.ValidationError(msg, code='authorization')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')
        else:
            msg = 'Must include "username" and "password".'
            raise serializers.ValidationError(msg, code='authorization')

        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):

    old_password = serializers.CharField(
        required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(
        required=True, style={'input_type': 'password'})
    confirme_password = serializers.CharField(
        required=True, style={'input_type': 'password'})

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirme_password']:
            raise serializers.ValidationError(
                {"new_password": "Password fields didn't match."})
        return attrs


class AdminRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email',
            'password', 'password2',
            'first_name', 'last_name',
            'phone_number'
        ]

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError(
                {"password": "Passwords don't match"})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')

        user = User.objects.create_user(**validated_data, password=password)

        try:
            admin_role = Role.objects.get(name='admin')
            user.roles.add(admin_role)

            user.role = 'admin'
            user.save()

        except Role.DoesNotExist:
            pass

        return user
