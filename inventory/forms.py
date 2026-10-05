from django import forms
from core.forms import BootstrapForm, BootstrapModelForm
from .models import Item, ExpiryWriteOff


class ItemForm(BootstrapModelForm):
    class Meta:
        model = Item
        fields = ["sku", "name", "description", "cost_price", "sale_price", "reorder_level", "has_expiry"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class ExpiryWriteOffForm(BootstrapModelForm):
    class Meta:
        model = ExpiryWriteOff
        fields = ["item", "quantity", "date_noticed", "note"]
        widgets = {
            "date_noticed": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


class StockAdjustmentForm(BootstrapForm):
    item = forms.ModelChoiceField(queryset=Item.objects.order_by("name"))
    quantity = forms.IntegerField(help_text="Positive to add stock, negative to remove.")
    note = forms.CharField(max_length=255, label="Reason")
