from django import forms
from django.utils import timezone
from core.forms import BootstrapForm

from invoices.models import InvoiceLine, Payment


class ReturnRecordForm(BootstrapForm):
    REFUND_CHOICES = [
        ("apply", "Apply as credit to another invoice"),
        ("refund", "Refund directly"),
    ]

    invoice_line = forms.ModelChoiceField(queryset=InvoiceLine.objects.none(), label="Invoice line")
    quantity = forms.IntegerField(min_value=1)
    date_returned = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    is_restockable = forms.BooleanField(required=False, initial=True, label="Restock returned items")
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    resolution = forms.ChoiceField(
        choices=REFUND_CHOICES,
        widget=forms.RadioSelect,
        initial="apply",
    )
    refund_method = forms.ChoiceField(
        choices=[("", "---")] + list(Payment.PAYMENT_METHODS),
        required=False,
        label="Refund method",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lines = InvoiceLine.objects.filter(invoice__status__in=["issued", "paid"]).select_related("invoice", "invoice__customer", "item").order_by("-invoice__created_at")
        available_ids = [line.pk for line in lines if line.available_qty > 0]
        self.fields["invoice_line"].queryset = InvoiceLine.objects.filter(pk__in=available_ids).select_related(
            "invoice", "invoice__customer", "item"
        ).order_by("-invoice__created_at")

    def clean(self):
        cleaned = super().clean()
        line = cleaned.get("invoice_line")
        quantity = cleaned.get("quantity")
        if line and quantity and quantity > line.available_qty:
            self.add_error("quantity", f"Only {line.available_qty} unaccounted units remain on this invoice line.")
        if cleaned.get("resolution") == "refund" and not cleaned.get("refund_method"):
            self.add_error("refund_method", "Choose a refund method.")
        return cleaned
