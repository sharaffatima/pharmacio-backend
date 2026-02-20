from django.db import models
import uuid
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager
)

# Create your models here.

class UserManager(BaseUserManager): # Custom user manager to handle user creation and superuser creation
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        user.set_password(password) # Hash the password using Django's built-in method to ensure security; This method takes care of hashing and salting the password, making it more secure than storing it in plain text
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields): # Create a superuser with the given email and password; Superuser is important for admin access and management of the application
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = UserManager()

    USERNAME_FIELD = "email" # Set the email field as the unique identifier for authentication instead of the default username field
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email