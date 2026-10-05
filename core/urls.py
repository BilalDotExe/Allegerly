from django.urls import path

from core import views



urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.AllegderlyLoginView.as_view(), name='login'),
    path('logout/', views.AllegderlyLogoutView.as_view(), name='logout'),
]
