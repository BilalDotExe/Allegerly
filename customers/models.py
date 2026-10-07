from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from core.money import money, zero_money
from decimal import Decimal

_ZERO = Value(Decimal('0.00'), output_field=DecimalField(max_digits=14, decimal_places=4))


# Issued + paid invoices count as billed (draft/voided do not).
_BILLED_STATUSES = ('issued', 'paid')

# Same tax % on every line of an invoice equals tax on the invoice subtotal.
_LINE_WITH_TAX = ExpressionWrapper(
    F('quantity') * F('unit_price') * (Value(1) + F('invoice__tax_percent') / Value(100)),
    output_field=DecimalField(max_digits=14, decimal_places=4),
)


class Customer(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(blank=True, max_length=20, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def _money_sum(self, aggregate):
        value = aggregate.get('total')
        if value is None:
            return zero_money()
        return money(value)

    def total_billed(self):
        """Sum of issued+paid invoice totals (lines + invoice tax)."""
        from invoices.models import InvoiceLine

        return self._money_sum(
            InvoiceLine.objects.filter(
                invoice__customer=self,
                invoice__status__in=_BILLED_STATUSES,
            ).aggregate(total=Coalesce(Sum(_LINE_WITH_TAX), _ZERO))
        )

    def total_paid(self):
        """Non-voided payments on billed (issued/paid) invoices."""
        from invoices.models import Payment

        return self._money_sum(
            Payment.objects.filter(
                invoice__customer=self,
                invoice__status__in=_BILLED_STATUSES,
                is_voided=False,
            ).aggregate(total=Coalesce(Sum('amount'), _ZERO))
        )

    def credits_applied(self):
        """Credit applications onto billed invoices."""
        from invoices.models import CreditApplication

        return self._money_sum(
            CreditApplication.objects.filter(
                credit_note__customer=self,
                invoice__status__in=_BILLED_STATUSES,
            ).aggregate(total=Coalesce(Sum('amount'), _ZERO))
        )

    def outstanding_balance(self):
        return money(self.total_billed() - self.total_paid() - self.credits_applied())

    def credit_balance(self):
        """Unapplied remainder of credit notes that have not been refunded."""
        from invoices.models import CreditNote

        return self._money_sum(
            CreditNote.objects.filter(
                customer=self,
                is_refunded=False,
            ).filter(
                remaining_amount__gt=0,
            ).aggregate(total=Coalesce(Sum('remaining_amount'), _ZERO))
        )

    def delete(self, *args, **kwargs):
        # History stays in the ledger; deactivate instead.
        if self.invoices.exists() or self.credit_notes.exists():
            raise ValidationError(
                'Customers with history cannot be deleted. Set is_active=False instead.'
            )
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.name
