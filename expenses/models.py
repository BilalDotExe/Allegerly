from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from businesses.db import atomic
from core.money import money
from core.numbering import next_sequential_code

_ZERO = Value(Decimal('0.00'), output_field=DecimalField(max_digits=14, decimal_places=2))

# Starter suggestions for the category box; anything typed before is suggested too.
DEFAULT_CATEGORIES = (
    'Rent', 'Utilities', 'Wages', 'Transport', 'Packaging', 'Supplies',
    'Repairs', 'Marketing', 'Fees',
)


def default_name(report_date):
    """What an expense is called when nobody typed a name, e.g. "Expense Nov 11, 2026"."""
    return f'Expense {report_date:%b} {report_date.day}, {report_date.year}'


class ExpenseReport(models.Model):
    """One batch of money spent, written up as a numbered report with typed lines."""

    report_number = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField('Title', max_length=200)
    report_date = models.DateField('Date')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-report_date', '-id']

    def save(self, *args, **kwargs):
        self.name = (self.name or '').strip()
        if not self.name and self.report_date:
            self.name = default_name(self.report_date)
        if self.pk is None and not self.report_number:
            with atomic():
                self.report_number = next_sequential_code(ExpenseReport.objects, 'report_number', 'EXP-')
                self.full_clean()
                super().save(*args, **kwargs)
            return
        if self.pk:
            original = ExpenseReport.objects.get(pk=self.pk)
            for field in ('report_number', 'created_by_id'):
                if getattr(self, field) != getattr(original, field):
                    raise ValidationError('The report number and creator cannot be changed.')
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Expense reports cannot be deleted.')

    @property
    def total(self):
        return money(self.lines.aggregate(total=Coalesce(Sum('amount'), _ZERO))['total'])

    def category_totals(self):
        """Subtotal per category, first-seen order; "rent" and "Rent" count as one."""
        totals = {}
        for line in self.lines.all():
            row = totals.setdefault(
                (line.category or '').lower(),
                {'category': line.category, 'count': 0, 'total': Decimal('0.00')},
            )
            row['count'] += 1
            row['total'] += line.amount
        return list(totals.values())

    def __str__(self):
        return f'{self.report_number} - {self.name}'


class ExpenseLine(models.Model):
    report = models.ForeignKey(ExpenseReport, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(
        max_length=200, blank=True, help_text='What the money was spent on. Free text.',
    )
    category = models.CharField(
        max_length=100, blank=True, help_text='Type any category; earlier ones are suggested.',
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    reference = models.CharField(
        max_length=100, blank=True, help_text='Receipt, cheque or transfer reference.',
    )

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        if self.amount is not None:
            self.amount = money(self.amount)
        self.category = (self.category or '').strip()
        self.reference = (self.reference or '').strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.report.report_number} | {self.description}'
