from django import forms
from core.forms import BootstrapModelForm

from inventory.models import Item

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inactive items can't be produced; an existing batch keeps its item.
        self.fields["item"].queryset = Item.objects.active_or(self.instance.item_id).order_by("name")
