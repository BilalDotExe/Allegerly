from django.urls import path

from . import views

app_name = "damages"

urlpatterns = [
    path("", views.damage_list, name="list"),
    path("new/", views.damage_create, name="create"),
]
