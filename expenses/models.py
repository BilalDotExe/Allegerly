from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.db.transaction import atomic

from core.money import money
from core.numbering import next_sequential_code

_ZERO = Value(Decimal('0.00'), output_field=DecimalField(max_digits=14, decimal_places=2))

# Starter dropdown options. Anything staff type is offered alongside these from
# then on, so the list grows with the business instead of boxing it in.
DEFAULT_CATEGORIES = (
    'Rent', 'Utilities', 'Wages', 'Transport', 'Packaging',
    'Supplies', 'Repairs', 'Marketing', 'Fees',
)


class ExpenseReport(models.Model):
    """One batch of money spent, written up as a numbered report with typed lines."""

    report_number = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField('Title', max_length=200)
    report_date = models.DateField('Date')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-report_date', '-id')

    def save(self, *args, **kwargs):
        if not self.pk:
            # The number is claimed under a row lock, so two people saving at
            # the same moment cannot land on the same EXP- code.
            with atomic():
                if not self.report_number:
                    self.report_number = next_sequential_code(
                        ExpenseReport.objects, 'report_number', 'EXP-'
                    )
                self.full_clean()
                super().save(*args, **kwargs)
            return

        # Records are append-only: the title, date, notes and lines stay
        # editable, but the identity of the report does not.
        previous = ExpenseReport.objects.get(pk=self.pk)
        if (previous.report_number, previous.created_by_id) != (self.report_number, self.created_by_id):
            raise ValidationError('The report number and creator cannot be changed.')
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Expense reports cannot be deleted.')

    @property
    def total(self):
        return money(self.lines.aggregate(total=Coalesce(Sum('amount'), _ZERO))['total'])

    @property
    def grouped_lines(self):
        """Lines bucketed by category (first-seen order, case-insensitive).

        Each line gets a line_no that restarts at 1 inside its category, matching
        the numbering on the entry form.
        """
        groups = {}
        for line in self.lines.all():
            group = groups.setdefault(line.category.lower(), {
                'category': line.category,
                'lines': [],
                'total': Decimal('0.00'),
            })
            line.line_no = len(group['lines']) + 1
            group['lines'].append(line)
            group['total'] += line.amount
        return list(groups.values())

    def __str__(self):
        return f'{self.report_number} - {self.name}'


class ExpenseLine(models.Model):
    report = models.ForeignKey(ExpenseReport, models.CASCADE, related_name='lines')
    description = models.CharField(max_length=200, help_text='What the money was spent on. Free text.')
    category = models.CharField(
        max_length=100, blank=True,
        help_text='Type any category; earlier ones are suggested.',
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        # Decimal, not '0': MinValueValidator compares with <, and
        # Decimal < str raises TypeError on every amount entered.
        validators=[MinValueValidator(Decimal('0'))],
    )
    reference = models.CharField(
        max_length=100, blank=True,
        help_text='Receipt, cheque or transfer reference.',
    )

    class Meta:
        ordering = ('id',)

    def save(self, *args, **kwargs):
        self.amount = money(self.amount)
        self.category = self.category.strip()
        self.reference = self.reference.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.report.report_number} | {self.description}'
