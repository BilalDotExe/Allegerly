from django import forms
from core.forms import BootstrapForm

from invoices.models import InvoiceLine
from inventory.models import Item


class DamageReportForm(BootstrapForm):
    item = forms.ModelChoiceField(queryset=Item.objects.order_by("name"))
    invoice_line = forms.ModelChoiceField(queryset=InvoiceLine.objects.none(), required=False)
    quantity = forms.IntegerField(min_value=1)
    date_reported = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invoice_line"].queryset = InvoiceLine.objects.select_related(
            "invoice", "item"
        ).order_by("-invoice__created_at")
