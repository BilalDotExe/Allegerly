from django.urls import path
from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("create/", views.customer_create, name="create"),
    path("<int:pk>/", views.customer_detail, name="detail"),
    path("<int:pk>/edit/", views.customer_edit, name="edit"),
    path("<int:pk>/receive-payment/", views.customer_receive_payment, name="receive_payment"),
    path("<int:pk>/statement/", views.customer_statement_print, name="statement"),
    path("<int:pk>/statement.csv", views.customer_statement_csv, name="statement_csv"),
]