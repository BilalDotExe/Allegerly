from decimal import Decimal

from django import forms
from django.utils import timezone

from core.forms import BootstrapForm, BootstrapModelForm, OptionalWithDefaultMixin, TableRowFormMixin
from reports.forms import DateRangeForm
from vendors.models import Vendor
from .models import PurchaseOrder, PurchaseOrderLine, PurchasePayment


class PurchaseOrderForm(OptionalWithDefaultMixin, BootstrapModelForm):
    # Only the vendor is required; the rest fall back to sensible defaults.
    optional_with_default = ("tax_percent", "shipping_cost")

    class Meta:
        model = PurchaseOrder
        fields = [
            "vendor", "order_date", "expected_date", "vendor_reference",
            "tax_percent", "shipping_cost", "notes",
        ]
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "expected_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        vendors = Vendor.objects.filter(is_active=True)
        self.fields["order_date"].required = False
        if self.instance.pk:
            vendors = Vendor.objects.filter(is_active=True) | Vendor.objects.filter(pk=self.instance.vendor_id)
            if self.instance.vendor_locked:
                self.fields["vendor"].disabled = True
        else:
            self.fields["order_date"].initial = timezone.localdate()
        self.fields["vendor"].queryset = vendors.order_by("name")

    def clean_order_date(self):
        return self.cleaned_data.get("order_date") or timezone.localdate()


class PurchaseOrderLineForm(TableRowFormMixin, BootstrapModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ["item_name", "quantity", "unit_cost"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quantity"].widget.attrs.update({"min": 1, "placeholder": "1"})
        self.fields["unit_cost"].widget.attrs.update({"min": 0, "step": "0.01", "placeholder": "0.00"})
        # The item name is the line's "name" and stays required.
        self.fields["quantity"].required = False
        self.fields["unit_cost"].required = False

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        return 1 if quantity is None else quantity

    def clean_unit_cost(self):
        cost = self.cleaned_data.get("unit_cost")
        return Decimal("0.00") if cost is None else cost


class BasePurchaseOrderLineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form) and form.instance.pk:
                if form.instance.received_qty:
                    raise forms.ValidationError(
                        f"{form.instance.item_name} has already been received and cannot be removed."
                    )


PurchaseOrderLineFormSet = forms.inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    formset=BasePurchaseOrderLineFormSet,
    extra=1,
    can_delete=True,
)


class PurchasePaymentForm(BootstrapModelForm):
    class Meta:
        model = PurchasePayment
        fields = ["amount", "method", "payment_date", "reference", "note"]
        widgets = {"payment_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_date"].initial = timezone.localdate()


class CancelOrderForm(BootstrapForm):
    reason = forms.CharField(max_length=255, label="Cancel reason")


class ReceiveHeaderForm(BootstrapForm):
    received_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    note = forms.CharField(max_length=255, required=False, label="Note (e.g. packing slip number)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["received_date"].initial = timezone.localdate()


class ReceiveLineForm(BootstrapForm):
    quantity = forms.IntegerField(min_value=0, label="Receive now")
    unit_cost = forms.DecimalField(
        min_value=Decimal("0"), max_digits=10, decimal_places=2, label="Buying price",
    )

    def __init__(self, *args, po_line, **kwargs):
        super().__init__(*args, **kwargs)
        self.po_line = po_line
        self.fields["quantity"].widget.attrs.update({"min": 0, "max": po_line.outstanding_qty})
        self.fields["unit_cost"].widget.attrs.update({"min": 0, "step": "0.01"})
        # Rendered as a table row, so the column header is the only visible label.
        # Name each input after its item or a screen reader just hears "edit box".
        for field in self.fields.values():
            field.widget.attrs["aria-label"] = f"{field.label} for {po_line.item_name}"
        if not self.is_bound:
            self.initial.setdefault("quantity", po_line.outstanding_qty)
            self.initial.setdefault("unit_cost", po_line.unit_cost)

    def clean_quantity(self):
        qty = self.cleaned_data["quantity"]
        if qty > self.po_line.outstanding_qty:
            raise forms.ValidationError(f"Only {self.po_line.outstanding_qty} still outstanding.")
        return qty


class PurchaseOrderFilterForm(DateRangeForm):
    pass
