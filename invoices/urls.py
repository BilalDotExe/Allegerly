from django.urls import path
from . import views

app_name = "invoices"

urlpatterns = [
    path("", views.invoice_list, name="list"),
    path("create/", views.invoice_create, name="create"),
    path("<int:pk>/", views.invoice_detail, name="detail"),
    path("<int:pk>/issue/", views.invoice_issue, name="issue"),
    path("<int:pk>/void/", views.invoice_void, name="void"),
    path("<int:pk>/payment/", views.payment_create, name="payment"),
    path("credits/", views.credit_list, name="credit_list"),
    path("credits/<int:pk>/", views.credit_detail, name="credit_detail"),
    path("credits/<int:pk>/apply/", views.credit_apply, name="credit_apply"),
    path("credits/<int:pk>/refund/", views.credit_mark_refunded, name="credit_refund"),
]