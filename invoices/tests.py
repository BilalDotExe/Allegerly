from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import CompanyProfile
from customers.models import Customer
from inventory.models import Item
from invoices.models import Invoice, InvoiceLine

DEFAULT_TEXT = "Bank: Acme\nAcct 123"


class PaymentInstructionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.client.force_login(self.user)
        self.cust = Customer.objects.create(first_name="Ada")
        self.item = Item.objects.create(sku="S1", name="Widget", cost_price=1, sale_price=5)
        company = CompanyProfile.load()
        company.payment_instructions = DEFAULT_TEXT
        company.save()

    def _create(self, **extra):
        data = {
            "customer": self.cust.pk, "payment_terms": "net_30", "tax_percent": "0",
            "issue_date": "2026-10-01", "due_date": "2026-10-31",
            "lines-TOTAL_FORMS": "1", "lines-INITIAL_FORMS": "0", "lines-MIN_NUM_FORMS": "1",
            "lines-MAX_NUM_FORMS": "1000", "lines-0-item": self.item.pk,
            "lines-0-quantity": "1", "lines-0-unit_price": "5",
        }
        data.update(extra)
        return self.client.post(reverse("invoices:create"), data)

    def test_new_invoice_form_prefilled_with_company_default(self):
        self.assertContains(self.client.get(reverse("invoices:create")), "Bank: Acme")

    def test_submitted_default_is_saved(self):
        self._create(payment_instructions=DEFAULT_TEXT)
        self.assertEqual(Invoice.objects.get().payment_instructions, DEFAULT_TEXT)

    def test_per_invoice_override_is_kept(self):
        self._create(payment_instructions="Pay cash on delivery")
        self.assertEqual(Invoice.objects.get().payment_instructions, "Pay cash on delivery")

    def test_clearing_the_field_is_respected(self):
        self._create(payment_instructions="")
        self.assertEqual(Invoice.objects.get().payment_instructions, "")

    def test_programmatic_invoice_copies_company_default(self):
        inv = Invoice.objects.create(customer=self.cust, created_by=self.user)
        self.assertEqual(inv.payment_instructions, DEFAULT_TEXT)

    def test_company_settings_saves_instructions(self):
        resp = self.client.post(reverse("account_settings"), {"name": "Acme", "payment_instructions": "Pay by cheque"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(CompanyProfile.load().payment_instructions, "Pay by cheque")

    def test_print_shows_instructions_and_terms(self):
        inv = Invoice.objects.create(customer=self.cust, created_by=self.user,
                                     issue_date="2026-10-01", due_date="2026-10-31")
        InvoiceLine.objects.create(invoice=inv, item=self.item, quantity=1, unit_price=5)
        Invoice.objects.filter(pk=inv.pk).update(status="issued")
        html = self.client.get(reverse("invoices:print", args=[inv.pk])).content.decode()
        self.assertIn("Payment instructions", html)
        self.assertIn("Acct 123", html)
        self.assertIn("Net 30", html)

    def test_detail_has_back_button_instructions_and_terms(self):
        inv = Invoice.objects.create(customer=self.cust, created_by=self.user,
                                     issue_date="2026-10-01", due_date="2026-10-31")
        html = self.client.get(reverse("invoices:detail", args=[inv.pk])).content.decode()
        self.assertIn("page-back-top", html)
        self.assertIn("Acct 123", html)
        self.assertIn("Net 30", html)

    def test_payment_terms_defaults_to_net_30(self):
        inv = Invoice.objects.create(customer=self.cust, created_by=self.user)
        self.assertEqual(inv.payment_terms, Invoice.TERMS_NET_30)
        self.assertEqual(inv.get_payment_terms_display(), "Net 30")

    def test_payment_terms_selectable_on_create(self):
        self._create(payment_terms=Invoice.TERMS_ON_RECEIPT)
        self.assertEqual(Invoice.objects.get().payment_terms, Invoice.TERMS_ON_RECEIPT)

    def test_payment_terms_locked_after_issue(self):
        inv = Invoice.objects.create(customer=self.cust, created_by=self.user,
                                     issue_date="2026-10-01", due_date="2026-10-31")
        InvoiceLine.objects.create(invoice=inv, item=self.item, quantity=1, unit_price=5)
        Invoice.objects.filter(pk=inv.pk).update(status="issued")
        inv.refresh_from_db()
        inv.payment_terms = Invoice.TERMS_NET_60
        with self.assertRaises(Exception):
            inv.save()


class LineDiscountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.customer = Customer.objects.create(first_name="Ada")
        self.item = Item.objects.create(sku="S1", name="Widget", cost_price=1, sale_price=10)
        self.invoice = Invoice.objects.create(customer=self.customer, created_by=self.user)

    def _line(self, discount_percent):
        return InvoiceLine(invoice=self.invoice, item=self.item, quantity=2,
                           unit_price=Decimal("10.00"), discount_percent=discount_percent)

    def test_discount_above_100_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._line(Decimal("150.00")).full_clean()

    def test_negative_discount_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._line(Decimal("-10.00")).full_clean()

    def test_discount_at_the_bounds_is_accepted(self):
        self._line(Decimal("0.00")).full_clean()
        self._line(Decimal("100.00")).full_clean()

    def test_credit_amount_for_prorates_the_discounted_total(self):
        line = self._line(Decimal("50.00"))
        self.assertEqual(line.line_total, Decimal("10.00"))
        self.assertEqual(line.credit_amount_for(1), Decimal("5.00"))
        self.assertEqual(line.credit_amount_for(2), Decimal("10.00"))


class MinimalInvoiceEntryTests(TestCase):
    """Only the customer and each line's item are required; everything else has a default."""

    def setUp(self):
        self.user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.client.force_login(self.user)
        self.cust = Customer.objects.create(first_name="Ada")
        self.item = Item.objects.create(sku="S1", name="Widget", cost_price=1, sale_price=5)

    def _post(self, **extra):
        data = {
            "customer": self.cust.pk, "payment_terms": "", "tax_percent": "",
            "issue_date": "", "due_date": "", "notes": "", "payment_instructions": "",
            "lines-TOTAL_FORMS": "1", "lines-INITIAL_FORMS": "0", "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000", "lines-0-item": self.item.pk,
            "lines-0-quantity": "", "lines-0-unit_price": "", "lines-0-discount_percent": "",
        }
        data.update(extra)
        return self.client.post(reverse("invoices:create"), data)

    def test_blank_terms_tax_quantity_and_price_use_defaults(self):
        self._post()
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.payment_terms, Invoice.TERMS_NET_30)
        self.assertEqual(invoice.tax_percent, Decimal("0.00"))
        line = invoice.lines.get()
        self.assertEqual(line.quantity, 1)
        self.assertEqual(line.unit_price, self.item.sale_price)
        self.assertEqual(line.discount_percent, Decimal("0"))

    def test_invoice_can_be_saved_with_no_lines(self):
        self._post(**{"lines-0-item": "", "lines-0-discount_percent": "0"})
        self.assertEqual(Invoice.objects.get().lines.count(), 0)

    def test_customer_and_line_item_stay_required(self):
        self._post(customer="")
        self.assertEqual(Invoice.objects.count(), 0)
        self._post(**{"lines-0-item": "", "lines-0-quantity": "4"})
        self.assertEqual(Invoice.objects.count(), 0)

    def test_line_numbers_on_form_detail_list_and_print(self):
        invoice = Invoice.objects.create(customer=self.cust, created_by=self.user, status="issued")
        for qty in (1, 2):
            InvoiceLine.objects.create(invoice=invoice, item=self.item, quantity=qty, unit_price=5)
        self.assertContains(self.client.get(reverse("invoices:create")), 'class="line-no">1</td>')
        self.assertContains(self.client.get(reverse("invoices:detail", args=[invoice.pk])), '<td class="col-line">2</td>')
        self.assertContains(self.client.get(reverse("invoices:list")), '<td class="col-line">2</td>')
        self.assertContains(self.client.get(reverse("invoices:print", args=[invoice.pk])), '<td class="ln">2</td>')
