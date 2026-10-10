from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.permissions import GROUP_STAFF, GROUP_VIEW_ONLY
from customers.models import Customer
from damages.forms import DamageReportForm
from damages.services import log_damage
from inventory.models import Item
from invoices.models import Invoice, InvoiceLine


class DamageCreditAmountTests(TestCase):
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
        _, credit = log_damage(item=self.item, quantity=10, date_reported="2026-10-02",
                               created_by=self.user, invoice_line=line, issue_credit=True)
        self.assertEqual(credit.amount, Decimal("75.00"))

    def test_fully_discounted_line_credits_nothing(self):
        line = self._issued_line(10, Decimal("10.00"), Decimal("100.00"))
        _, credit = log_damage(item=self.item, quantity=10, date_reported="2026-10-02",
                               created_by=self.user, invoice_line=line, issue_credit=True)
        self.assertEqual(credit.amount, Decimal("0.00"))

    def test_credit_never_exceeds_what_the_line_billed(self):
        line = self._issued_line(4, Decimal("7.33"), Decimal("12.50"))
        _, credit = log_damage(item=self.item, quantity=4, date_reported="2026-10-02",
                               created_by=self.user, invoice_line=line, issue_credit=True)
        self.assertEqual(credit.amount, line.line_total)

    def test_partial_damage_credits_its_share(self):
        line = self._issued_line(10, Decimal("10.00"), Decimal("50.00"))
        _, credit = log_damage(item=self.item, quantity=3, date_reported="2026-10-02",
                               created_by=self.user, invoice_line=line, issue_credit=True)
        self.assertEqual(credit.amount, Decimal("15.00"))

    def test_draft_invoice_lines_are_not_selectable(self):
        draft = Invoice.objects.create(customer=self.customer, created_by=self.user)
        draft_line = InvoiceLine.objects.create(invoice=draft, item=self.item,
                                                quantity=1, unit_price=Decimal("10.00"))
        issued_line = self._issued_line(1, Decimal("10.00"), Decimal("0.00"))
        selectable = DamageReportForm().fields["invoice_line"].queryset
        self.assertIn(issued_line, selectable)
        self.assertNotIn(draft_line, selectable)


class DamageViewAccessTests(TestCase):
    def setUp(self):
        self.item = Item.objects.create(sku="S1", name="Widget", cost_price=1, sale_price=10)

    def test_user_with_no_group_is_denied(self):
        self.client.force_login(User.objects.create_user("nobody", password="pw"))
        self.assertEqual(self.client.get(reverse("damages:create")).status_code, 403)

    def test_view_only_cannot_post_a_damage_report(self):
        user = User.objects.create_user("reader", password="pw")
        user.groups.add(Group.objects.get(name=GROUP_VIEW_ONLY))
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("damages:create")).status_code, 200)
        response = self.client.post(reverse("damages:create"), {
            "item": self.item.pk, "quantity": "1", "date_reported": "2026-10-02",
        })
        self.assertEqual(response.status_code, 403)
