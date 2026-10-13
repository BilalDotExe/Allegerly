from django import forms
from core.forms import BootstrapModelForm

from .models import ProductionBatch


class ProductionBatchForm(BootstrapModelForm):
    has_expiry = forms.BooleanField(
        required=False, label="This batch has an expiry date",
        help_text="Tick to record when it goes off.",
    )

    class Meta:
        model = ProductionBatch
        fields = ["item", "quantity_produced", "production_date", "has_expiry", "expiry_date", "note"]
        widgets = {
            "production_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date", "data-calendar-below": ""}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expiry_date"].required = False
        self.fields["has_expiry"].initial = bool(self.instance.pk and self.instance.expiry_date)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("has_expiry"):
            cleaned["expiry_date"] = None
        return cleaned
