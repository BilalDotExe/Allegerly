from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from core.money import money


class Vendor(models.Model):
    CATEGORY_RAW_MATERIALS = 'raw_materials'
    CATEGORY_PACKAGING = 'packaging'
    CATEGORY_EQUIPMENT = 'equipment'
    CATEGORY_SERVICES = 'services'
    CATEGORY_UTILITIES = 'utilities'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_RAW_MATERIALS, 'Raw materials'),
        (CATEGORY_PACKAGING, 'Packaging'),
        (CATEGORY_EQUIPMENT, 'Equipment & supplies'),
        (CATEGORY_SERVICES, 'Services'),
        (CATEGORY_UTILITIES, 'Utilities'),
        (CATEGORY_OTHER, 'Other'),
    ]

    TERMS_ON_RECEIPT = 'due_on_receipt'
    TERMS_NET_15 = 'net_15'
    TERMS_NET_30 = 'net_30'
    TERMS_NET_45 = 'net_45'
    TERMS_NET_60 = 'net_60'
    TERMS_CHOICES = [
        (TERMS_ON_RECEIPT, 'Due on receipt'),
        (TERMS_NET_15, 'Net 15'),
        (TERMS_NET_30, 'Net 30'),
        (TERMS_NET_45, 'Net 45'),
        (TERMS_NET_60, 'Net 60'),
    ]

    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(blank=True, max_length=20, null=True)
    address = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    tax_id = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='Tax ID / GSTIN',
        help_text="Vendor's tax registration number, if any.",
    )
    payment_terms = models.CharField(max_length=20, choices=TERMS_CHOICES, default=TERMS_NET_30)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def outstanding_payable(self):
        """What we still owe this vendor on placed purchase orders."""
        orders = self.purchase_orders.filter(status__in=('ordered', 'partial', 'received'))
        return money(sum((po.balance_due for po in orders), Decimal('0')))

    def __str__(self):
        return self.name
