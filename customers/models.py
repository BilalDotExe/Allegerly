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
    F('quantity') * F('unit_price') * (Value(Decimal('1')) + F('invoice__tax_percent') / Value(Decimal('100'))),
    output_field=DecimalField(max_digits=14, decimal_places=4),
)


class Customer(models.Model):
    TYPE_RETAIL = 'retail'
    TYPE_WHOLESALE = 'wholesale'
    TYPE_CHOICES = [
        (TYPE_RETAIL, 'Retail'),
        (TYPE_WHOLESALE, 'Wholesale'),
    ]

    # Display name, rebuilt from the name parts on every save (used by lists, reports, queries).
    name = models.CharField(max_length=300, editable=False)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    print_name = models.CharField(
        'Name to print on invoice', max_length=200, blank=True,
        help_text='Leave blank to use the customer name.',
    )
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(blank=True, max_length=20, null=True)
    website = models.URLField(blank=True)
    customer_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_RETAIL)

    billing_line1 = models.CharField('Street address', max_length=200, blank=True)
    billing_line2 = models.CharField('Apt, suite, unit', max_length=200, blank=True)
    billing_city = models.CharField('City', max_length=100, blank=True)
    billing_state = models.CharField('State / province', max_length=100, blank=True)
    billing_postal_code = models.CharField('ZIP / postal code', max_length=20, blank=True)
    billing_country = models.CharField('Country', max_length=100, blank=True)

    shipping_same_as_billing = models.BooleanField(default=True)
    shipping_line1 = models.CharField('Street address', max_length=200, blank=True)
    shipping_line2 = models.CharField('Apt, suite, unit', max_length=200, blank=True)
    shipping_city = models.CharField('City', max_length=100, blank=True)
    shipping_state = models.CharField('State / province', max_length=100, blank=True)
    shipping_postal_code = models.CharField('ZIP / postal code', max_length=20, blank=True)
    shipping_country = models.CharField('Country', max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_wholesale(self):
        return self.customer_type == self.TYPE_WHOLESALE

    @staticmethod
    def _address_lines(line1, line2, city, state, postal_code, country):
        locality = ', '.join(p for p in (city, state) if p)
        if postal_code:
            locality = f'{locality} {postal_code}'.strip()
        return [x for x in (line1, line2, locality, country) if x]

    @property
    def billing_address_lines(self):
        return self._address_lines(
            self.billing_line1, self.billing_line2, self.billing_city,
            self.billing_state, self.billing_postal_code, self.billing_country,
        )

    @property
    def shipping_address_lines(self):
        if self.shipping_same_as_billing:
            return self.billing_address_lines
        return self._address_lines(
            self.shipping_line1, self.shipping_line2, self.shipping_city,
            self.shipping_state, self.shipping_postal_code, self.shipping_country,
        )

    @property
    def invoice_name(self):
        return self.print_name or self.name

    def save(self, *args, **kwargs):
        self.name = ' '.join(p for p in (self.first_name, self.middle_name, self.last_name) if p)
        super().save(*args, **kwargs)

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
