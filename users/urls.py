from django.urls import path
from rest_framework.authtoken import views as token_views
from . import views

app_name = 'users'

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),

    path('auth/profile/', views.UserProfileView.as_view(), name='profile'),
    path('auth/change-password/',
         views.ChangePasswordView.as_view(), name='change-password'),

    path('auth/admin/register/', views.AdminRegisterView.as_view(),
         name='admin-register'),  


]
