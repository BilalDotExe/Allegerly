from django import forms
from django.utils import timezone

from core.forms import BootstrapForm, BootstrapModelForm, ContactAutocompleteMixin
from invoices.models import Payment
from .models import Customer

_SHIPPING_FIELDS = (
    "shipping_line1", "shipping_line2", "shipping_city",
    "shipping_state", "shipping_postal_code", "shipping_country",
)


class CustomerForm(ContactAutocompleteMixin, BootstrapModelForm):
    class Meta:
        model = Customer
        fields = [
            "first_name", "middle_name", "last_name", "company_name", "print_name",
            "email", "phone", "website", "customer_type",
            "billing_line1", "billing_line2", "billing_city",
            "billing_state", "billing_postal_code", "billing_country",
            "shipping_same_as_billing", *_SHIPPING_FIELDS,
            "is_active",
        ]

    def billing_open(self):
        """Expand the address dropdown when it holds data or errors."""
        names = [f for f in self.fields if f.startswith(("billing_", "shipping_")) and f != "shipping_same_as_billing"]
        has_value = any(self[n].value() for n in names)
        has_error = any(self[n].errors for n in names)
        return has_value or has_error or not self["shipping_same_as_billing"].value()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("shipping_same_as_billing"):
            for field in _SHIPPING_FIELDS:
                cleaned[field] = ""
        elif not cleaned.get("shipping_line1"):
            self.add_error("shipping_line1", "Enter a shipping address or tick 'Shipping address is the same as billing'.")
        return cleaned


class ReceivePaymentForm(BootstrapForm):
    """Header of the receive-payment screen. The per-invoice amounts are read straight
    from POST (pay_<invoice pk>) by the view, since the rows are built from live balances."""

    payment_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    method = forms.ChoiceField(choices=Payment.PAYMENT_METHODS, label="Payment method")
    amount_received = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "inputmode": "decimal", "placeholder": "0.00"}),
        help_text="Type an amount to apply it to the oldest invoices first, or fill in the invoices yourself.",
    )
    note = forms.CharField(max_length=255, required=False, label="Reference / note")
