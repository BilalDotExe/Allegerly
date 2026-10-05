from django.urls import path

from . import views

app_name = "production"

urlpatterns = [
    path("", views.production_list, name="list"),
    path("new/", views.production_create, name="create"),
]
