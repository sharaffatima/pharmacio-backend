from django.urls import path
from . import views

app_name = 'rbac'

urlpatterns = [
    path('permissions/', views.PermissionListView.as_view(), name='permission-list'),
    path('permissions/<int:pk>/', views.PermissionDetailView.as_view(),
         name='permission-detail'),

    path('roles/', views.RoleListView.as_view(), name='role-list'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role-detail'),

    path('roles/<int:role_id>/permissions/',
         views.RolePermissionsView.as_view(), name='role-permissions'),

    path('users/<int:user_id>/roles/',
         views.UserRolesView.as_view(), name='user-roles'),
    path('users/<int:user_id>/roles/<int:role_id>/',
         views.UserRemoveRoleView.as_view(), name='user-role-remove'),

    path('check-permission/', views.CheckPermissionView.as_view(),
         name='check-permission'),
]
