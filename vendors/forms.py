from django import forms
from core.forms import BootstrapModelForm, ContactAutocompleteMixin
from .models import Vendor


class VendorForm(ContactAutocompleteMixin, BootstrapModelForm):
    class Meta:
        model = Vendor
        fields = [
            "name", "contact_person", "phone", "email", "address",
            "category", "tax_id", "payment_terms", "notes", "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3, "autocomplete": "street-address"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
