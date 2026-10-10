from decimal import Decimal

from django import forms
from core.forms import BootstrapForm, BootstrapModelForm, TableRowFormMixin
from core.models import CompanyProfile
from .models import Invoice, InvoiceLine, Payment, CreditNote
from customers.models import Customer
from inventory.models import Item


class InvoiceChoiceField(forms.ModelChoiceField):
    """Invoice dropdowns show more than the model's own `invoice_number` —
    picking the right invoice by number alone is near-impossible once a
    customer has more than a few, so every option also carries who it's for
    and roughly when."""

    def label_from_instance(self, obj):
        when = obj.issue_date or obj.created_at.date()
        return f"{obj.invoice_number} — {obj.customer.name} — {when.day} {when:%b}"


class InvoiceLineChoiceField(forms.ModelChoiceField):
    """Same reasoning as InvoiceChoiceField, plus the item/quantity since an
    invoice can have several lines."""

    def label_from_instance(self, obj):
        invoice = obj.invoice
        when = invoice.issue_date or invoice.created_at.date()
        return (
            f"{invoice.invoice_number} — {invoice.customer.name} — {when.day} {when:%b} "
            f"— {obj.item.name} x{obj.quantity}"
        )


class InvoiceForm(BootstrapModelForm):
    class Meta:
        model = Invoice
        fields = ["customer", "payment_terms", "tax_percent", "issue_date", "due_date", "notes", "payment_instructions"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "payment_instructions": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["payment_instructions"]
        field.empty_value = ""
        field.help_text = "Starts as your company default (Company settings). Change it here for this invoice only."
        if not self.instance.pk:
            field.initial = CompanyProfile.load().payment_instructions

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get("customer")
        tax_percent = cleaned_data.get("tax_percent")
        if customer and customer.is_wholesale and tax_percent:
            self.add_error("tax_percent", "Tax cannot be applied to wholesale customers.")
        return cleaned_data


class InvoiceLineForm(TableRowFormMixin, BootstrapModelForm):
    discount_percent = forms.DecimalField(
        required=False,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
        initial=Decimal('0'),
        label="Discount %",
        widget=forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "100"}),
    )

    class Meta:
        model = InvoiceLine
        fields = ["item", "quantity", "unit_price", "discount_percent"]

    def clean_discount_percent(self):
        val = self.cleaned_data.get('discount_percent')
        return val if val is not None else Decimal('0')


InvoiceLineFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceLine,
    form=InvoiceLineForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PaymentForm(BootstrapModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "payment_date", "note"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
        }


class VoidInvoiceForm(BootstrapForm):
    reason = forms.CharField(max_length=255, label="Void reason")


class ApplyCreditForm(BootstrapForm):
    credit_note = forms.ModelChoiceField(queryset=CreditNote.objects.none(), label="Credit Note")
    amount = forms.DecimalField(max_digits=10, decimal_places=2)

    def __init__(self, customer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["credit_note"].queryset = CreditNote.objects.filter(
            customer=customer, is_applied=False, is_refunded=False
        )


class MarkRefundedForm(BootstrapForm):
    refund_method = forms.ChoiceField(choices=Payment.PAYMENT_METHODS)
    refund_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
