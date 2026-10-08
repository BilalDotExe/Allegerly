from django import forms
from core.forms import BootstrapForm, BootstrapModelForm, TableRowFormMixin
from .models import Invoice, InvoiceLine, Payment, CreditNote
from customers.models import Customer
from inventory.models import Item


class InvoiceForm(BootstrapModelForm):
    class Meta:
        model = Invoice
        fields = ["customer", "tax_percent", "issue_date", "due_date", "notes"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get("customer")
        tax_percent = cleaned_data.get("tax_percent")
        if customer and customer.is_wholesale and tax_percent:
            self.add_error("tax_percent", "Tax cannot be applied to wholesale customers.")
        return cleaned_data


class InvoiceLineForm(TableRowFormMixin, BootstrapModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["item", "quantity", "unit_price"]


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
