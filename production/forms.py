from django import forms
from core.forms import BootstrapModelForm

from .models import ProductionBatch


class ProductionBatchForm(BootstrapModelForm):
    class Meta:
        model = ProductionBatch
        fields = ["item", "quantity_produced", "production_date", "expiry_date", "note"]
        widgets = {
            "production_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }
