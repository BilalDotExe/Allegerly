from django.test import TestCase

# Create your tests here.


from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse

from core.models import CompanyProfile
from customers.models import Customer
from invoices.models import Invoice, InvoiceLine
from inventory.models import Item


class CustomerAddressAndNameTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.client.force_login(self.user)

    def _post(self, **extra):
        data = {"first_name": "Ada", "customer_type": "retail", "is_active": "on",
                "shipping_same_as_billing": "on"}
        data.update(extra)
        return self.client.post(reverse("customers:create"), data)

    def test_first_name_required_and_name_built_from_parts(self):
        self.assertEqual(self._post(first_name="").status_code, 200)
        self.assertEqual(Customer.objects.count(), 0)
        self._post(first_name="Ada", middle_name="M", last_name="Lovelace")
        self.assertEqual(Customer.objects.get().name, "Ada M Lovelace")

    def test_same_as_billing_clears_shipping_fields(self):
        self._post(billing_line1="1 Main St", shipping_line1="stale")
        c = Customer.objects.get()
        self.assertEqual(c.shipping_line1, "")
        self.assertEqual(c.shipping_address_lines, c.billing_address_lines)

    def test_different_shipping_requires_address(self):
        r = self._post(billing_line1="1 Main St", shipping_same_as_billing="")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Customer.objects.count(), 0)
        self._post(billing_line1="1 Main St", shipping_same_as_billing="",
                   shipping_line1="9 Dock Rd", shipping_city="Port")
        c = Customer.objects.get()
        self.assertEqual(c.shipping_address_lines, ["9 Dock Rd", "Port"])

    def test_invoice_name_prefers_print_name(self):
        c = Customer.objects.create(first_name="Ada", last_name="L", print_name="Ada Ltd.")
        self.assertEqual(c.invoice_name, "Ada Ltd.")


class InvoicePrintDetailsTests(TestCase):
    def test_print_shows_company_and_both_addresses(self):
        user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.client.force_login(user)
        company = CompanyProfile.load()
        company.name, company.address_line1, company.city = "Acme Foods", "5 Mill Rd", "Leeds"
        company.save()
        cust = Customer.objects.create(
            first_name="Ada", print_name="Ada Trading", billing_line1="1 Main St",
            shipping_same_as_billing=False, shipping_line1="9 Dock Rd",
        )
        item = Item.objects.create(sku="S1", name="Widget", cost_price=1, sale_price=5)
        inv = Invoice.objects.create(customer=cust, created_by=user)
        InvoiceLine.objects.create(invoice=inv, item=item, quantity=1, unit_price=5)
        Invoice.objects.filter(pk=inv.pk).update(status="issued")
        html = self.client.get(reverse("invoices:print", args=[inv.pk])).content.decode()
        for text in ("Acme Foods", "5 Mill Rd", "Ada Trading", "1 Main St", "Ship To", "9 Dock Rd"):
            self.assertIn(text, html)

    def test_account_settings_admin_only(self):
        staff = User.objects.create_user("clerk", password="pw")
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("account_settings")).status_code, 403)


class ReceivePaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.client.force_login(self.user)
        self.cust = Customer.objects.create(first_name="Ada")
        self.item = Item.objects.create(sku="S1", name="Widget", cost_price=1, sale_price=5)
        self.url = reverse("customers:receive_payment", args=[self.cust.pk])
        # Three issued invoices of $100, $50, $30 — created oldest first.
        self.invoices = [self._invoice(price, f"2026-0{n}-01") for n, price in ((1, 100), (2, 50), (3, 30))]

    def _invoice(self, price, issue_date, customer=None):
        inv = Invoice.objects.create(customer=customer or self.cust, created_by=self.user, issue_date=issue_date)
        InvoiceLine.objects.create(invoice=inv, item=self.item, quantity=1, unit_price=price)
        Invoice.objects.filter(pk=inv.pk).update(status="issued")
        inv.refresh_from_db()
        return inv

    def _post(self, **data):
        base = {"payment_date": "2026-10-07", "method": "cash"}
        base.update(data)
        return self.client.post(self.url, base)

    def _balances(self):
        return [Invoice.objects.get(pk=i.pk).balance_due for i in self.invoices]

    def test_lump_sum_pays_oldest_first(self):
        resp = self._post(amount_received="120.00")
        self.assertRedirects(resp, reverse("customers:detail", args=[self.cust.pk]))
        self.assertEqual([str(b) for b in self._balances()], ["0.00", "30.00", "30.00"])
        self.assertEqual(Invoice.objects.get(pk=self.invoices[0].pk).status, "paid")
        self.assertEqual(Invoice.objects.get(pk=self.invoices[1].pk).status, "issued")

    def test_per_invoice_amounts_applied_as_typed(self):
        self._post(**{f"pay_{self.invoices[2].pk}": "30.00", f"pay_{self.invoices[0].pk}": "40.00"})
        self.assertEqual([str(b) for b in self._balances()], ["60.00", "50.00", "0.00"])

    def test_overpaying_the_customer_total_is_rejected(self):
        resp = self._post(amount_received="500.00")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "more than the")
        self.assertEqual([str(b) for b in self._balances()], ["100.00", "50.00", "30.00"])

    def test_row_over_its_balance_is_rejected_and_nothing_saved(self):
        resp = self._post(**{f"pay_{self.invoices[0].pk}": "10", f"pay_{self.invoices[1].pk}": "75"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "More than the")
        self.assertEqual([str(b) for b in self._balances()], ["100.00", "50.00", "30.00"])

    def test_mismatched_received_and_rows_is_rejected(self):
        resp = self._post(amount_received="90", **{f"pay_{self.invoices[0].pk}": "40"})
        self.assertContains(resp, "doesn&#x27;t match")
        self.assertEqual(self._balances()[0], Invoice.objects.get(pk=self.invoices[0].pk).total)

    def test_empty_submission_is_rejected(self):
        self.assertContains(self._post(), "Enter an amount received")

    def test_garbage_row_amount_shows_error(self):
        resp = self._post(**{f"pay_{self.invoices[0].pk}": "abc"})
        self.assertContains(resp, "Enter a number.")

    def test_other_customers_and_non_issued_invoices_are_not_listed(self):
        other = Customer.objects.create(first_name="Bob")
        self._invoice(999, "2026-01-01", customer=other)
        Invoice.objects.create(customer=self.cust, created_by=self.user)  # a draft
        resp = self.client.get(self.url)
        self.assertEqual(len(resp.context["rows"]), 3)

    def test_cannot_pay_another_customers_invoice_by_forging_a_field(self):
        other = Customer.objects.create(first_name="Bob")
        foreign = self._invoice(80, "2026-01-01", customer=other)
        self._post(**{f"pay_{foreign.pk}": "80"})
        self.assertEqual(Invoice.objects.get(pk=foreign.pk).balance_due, Invoice.objects.get(pk=foreign.pk).total)

    def test_detail_lists_invoices_and_button(self):
        resp = self.client.get(reverse("customers:detail", args=[self.cust.pk]))
        self.assertContains(resp, "Receive payment")
        self.assertContains(resp, self.invoices[0].invoice_number)

    def test_fully_paid_customer_has_no_button_and_empty_screen(self):
        self._post(amount_received="180")
        resp = self.client.get(reverse("customers:detail", args=[self.cust.pk]))
        self.assertNotContains(resp, "Receive payment")
        self.assertContains(self.client.get(self.url), "Nothing owing")

    def test_employee_cannot_open_screen(self):
        from django.contrib.auth.models import Group
        emp = User.objects.create_user("emp", password="pw")
        emp.groups.add(Group.objects.get(name="Employee"))
        self.client.force_login(emp)
        self.assertEqual(self.client.get(self.url).status_code, 403)


class CustomerStatementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.client.force_login(self.user)
        self.cust = Customer.objects.create(first_name="Ada")
        self.item = Item.objects.create(sku="S1", name="Widget", cost_price=1, sale_price=5)

    def _invoice(self, price, issue_date):
        inv = Invoice.objects.create(customer=self.cust, created_by=self.user, issue_date=issue_date)
        InvoiceLine.objects.create(invoice=inv, item=self.item, quantity=1, unit_price=price)
        Invoice.objects.filter(pk=inv.pk).update(status="issued")
        inv.refresh_from_db()
        return inv

    def test_statement_csv_lists_invoice_and_running_balance(self):
        self._invoice(100, "2026-01-01")
        self._invoice(50, "2026-02-01")
        resp = self.client.get(reverse("customers:statement_csv", args=[self.cust.pk]))
        self.assertEqual(resp["Content-Type"], "text/csv")
        body = resp.content.decode()
        self.assertIn("100.00", body)
        self.assertIn("150.00", body)  # running balance after both invoices

    def test_statement_csv_reflects_payments(self):
        from invoices.services import record_payment
        inv = self._invoice(100, "2026-01-01")
        record_payment(inv, 40, "cash", "2026-01-15", self.user)
        body = self.client.get(reverse("customers:statement_csv", args=[self.cust.pk])).content.decode()
        self.assertIn("60.00", body)  # balance due after partial payment

    def test_statement_print_renders(self):
        self._invoice(100, "2026-01-01")
        resp = self.client.get(reverse("customers:statement", args=[self.cust.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Statement")
        self.assertContains(resp, self.cust.name)

    def test_empty_statement_shows_no_activity(self):
        resp = self.client.get(reverse("customers:statement", args=[self.cust.pk]))
        self.assertContains(resp, "No activity")

    def test_voided_invoice_excluded_from_statement(self):
        from invoices.services import void_invoice
        inv = self._invoice(100, "2026-01-01")
        void_invoice(inv, self.user, "mistake")
        inv.refresh_from_db()
        rows, closing = self.customer_statement_rows()
        self.assertEqual(len(rows), 0)
        self.assertEqual(closing, Decimal("0.00"))

    def customer_statement_rows(self):
        from .statement import build_statement
        return build_statement(self.cust)

    def test_employee_cannot_access_statement(self):
        from django.contrib.auth.models import Group
        emp = User.objects.create_user("emp", password="pw")
        emp.groups.add(Group.objects.get(name="Employee"))
        self.client.force_login(emp)
        self.assertEqual(self.client.get(reverse("customers:statement", args=[self.cust.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("customers:statement_csv", args=[self.cust.pk])).status_code, 403)

    def test_list_page_has_row_expand_and_full_profile_link(self):
        resp = self.client.get(reverse("customers:list"))
        self.assertContains(resp, "row-expand")
        self.assertContains(resp, "Open full profile")
