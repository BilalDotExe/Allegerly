from django import forms
from core.forms import BootstrapModelForm
from .models import Customer

class CustomerForm(BootstrapModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "address", "is_active"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }
