from django.urls import path

from core import views



urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.account_settings, name='account_settings'),
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/new/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/reset-password/', views.employee_reset_password, name='employee_reset_password'),
    path('employees/<int:pk>/toggle-active/', views.employee_toggle_active, name='employee_toggle_active'),
    path('employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),
    path('login/', views.AllegderlyLoginView.as_view(), name='login'),
    path('logout/', views.AllegderlyLogoutView.as_view(), name='logout'),
]
