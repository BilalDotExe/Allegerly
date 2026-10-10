from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.permissions import GROUP_STAFF, GROUP_VIEW_ONLY
from customers.models import Customer
from inventory.models import Item
from invoices.models import Invoice, InvoiceLine
from returns.services import log_return


class ReturnCreditAmountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("staff", password="pw")
        self.user.groups.add(Group.objects.get(name=GROUP_STAFF))
        self.customer = Customer.objects.create(first_name="Ada")
        self.item = Item.objects.create(sku="S1", name="Widget", cost_price=1, sale_price=10)

    def _issued_line(self, quantity, unit_price, discount_percent):
        invoice = Invoice.objects.create(customer=self.customer, created_by=self.user,
                                         issue_date="2026-10-01", due_date="2026-10-31")
        line = InvoiceLine.objects.create(invoice=invoice, item=self.item, quantity=quantity,
                                          unit_price=unit_price, discount_percent=discount_percent)
        Invoice.objects.filter(pk=invoice.pk).update(status="issued")
        return line

    def test_credit_carries_the_line_discount(self):
        line = self._issued_line(10, Decimal("10.00"), Decimal("25.00"))
        _, credit = log_return(invoice_line=line, quantity=10, date_returned="2026-10-02",
                               created_by=self.user, is_restockable=False)
        self.assertEqual(credit.amount, Decimal("75.00"))

    def test_full_return_credits_exactly_the_line_total(self):
        line = self._issued_line(3, Decimal("4.99"), Decimal("33.33"))
        _, credit = log_return(invoice_line=line, quantity=3, date_returned="2026-10-02",
                               created_by=self.user, is_restockable=False)
        self.assertEqual(credit.amount, line.line_total)


class ReturnViewAccessTests(TestCase):
    def test_user_with_no_group_is_denied(self):
        self.client.force_login(User.objects.create_user("nobody", password="pw"))
        self.assertEqual(self.client.get(reverse("returns:create")).status_code, 403)

    def test_view_only_cannot_post_a_return(self):
        user = User.objects.create_user("reader", password="pw")
        user.groups.add(Group.objects.get(name=GROUP_VIEW_ONLY))
        self.client.force_login(user)
        self.assertEqual(self.client.post(reverse("returns:create"), {}).status_code, 403)
