from django import forms
from core.forms import BootstrapForm, BootstrapModelForm
from .models import Item, ExpiryWriteOff


class ItemForm(BootstrapModelForm):
    class Meta:
        model = Item
        fields = ["sku", "name", "description", "cost_price", "sale_price", "reorder_level", "has_expiry", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"is_active": "Active"}
        help_texts = {"is_active": "Untick to stop selling this item while keeping its history."}


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
