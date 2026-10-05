from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.item_list, name="list"),
    path("create/", views.item_create, name="create"),
    path("<int:pk>/", views.item_detail, name="detail"),
    path("<int:pk>/edit/", views.item_edit, name="edit"),
    path("movements/", views.movements_list, name="movements"),
    path("expiry/", views.expiry_list, name="expiry_list"),
    path("expiry/create/", views.expiry_create, name="expiry_create"),
    path("adjust/", views.stock_adjust, name="adjust"),
]