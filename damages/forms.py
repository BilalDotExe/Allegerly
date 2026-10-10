from django import forms
from core.forms import BootstrapForm

from invoices.forms import InvoiceLineChoiceField
from invoices.models import InvoiceLine, Payment
from inventory.models import Item


class DamageReportForm(BootstrapForm):
    RESOLUTION_CHOICES = [
        ("apply", "Apply as credit to another invoice"),
        ("refund", "Refund directly"),
    ]

    item = forms.ModelChoiceField(queryset=Item.objects.order_by("name"))
    invoice_line = InvoiceLineChoiceField(
        queryset=InvoiceLine.objects.none(), required=False, label="Invoice line (optional)",
        help_text="Link this damage to the sale it came from, for traceability.",
    )
    quantity = forms.IntegerField(min_value=1)
    date_reported = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    issue_credit = forms.BooleanField(
        required=False,
        label="Issue a credit note to the customer for this damaged quantity",
    )
    resolution = forms.ChoiceField(
        choices=RESOLUTION_CHOICES,
        widget=forms.RadioSelect,
        initial="apply",
        required=False,
    )
    refund_method = forms.ChoiceField(
        choices=[("", "---")] + list(Payment.PAYMENT_METHODS),
        required=False,
        label="Refund method",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only lines of a real sale, with units left to account for. A draft or
        # voided invoice never billed the customer, so it can't back a credit note.
        lines = InvoiceLine.objects.filter(
            invoice__status__in=["issued", "paid"]
        ).select_related("invoice", "item")
        available_ids = [line.pk for line in lines if line.available_qty > 0]
        self.fields["invoice_line"].queryset = InvoiceLine.objects.filter(
            pk__in=available_ids
        ).select_related("invoice", "invoice__customer", "item").order_by("-invoice__created_at")

    def clean(self):
        cleaned = super().clean()
        line = cleaned.get("invoice_line")
        quantity = cleaned.get("quantity")
        issue_credit = cleaned.get("issue_credit")
        if line and quantity and quantity > line.available_qty:
            self.add_error("quantity", f"Only {line.available_qty} unaccounted units remain on this invoice line.")
        if issue_credit:
            if not line:
                self.add_error("invoice_line", "Select the invoice line this credit applies to.")
            if cleaned.get("resolution") == "refund" and not cleaned.get("refund_method"):
                self.add_error("refund_method", "Choose a refund method.")
        return cleaned
