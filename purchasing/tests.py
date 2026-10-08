from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from audit.models import AuditLog
from vendors.models import Vendor
from .models import PurchaseOrder, PurchaseOrderLine
from .services import (
    cancel_order,
    close_order,
    place_order,
    receive_goods,
    record_purchase_payment,
)


class PurchasingBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.vendor = Vendor.objects.create(name="Acme Supply")

    def make_po(self, place=True, tax="10", shipping="5"):
        po = PurchaseOrder.objects.create(
            vendor=self.vendor, order_date=date(2026, 1, 1), created_by=self.user,
            tax_percent=Decimal(tax), shipping_cost=Decimal(shipping),
        )
        self.l_flour = PurchaseOrderLine.objects.create(
            purchase_order=po, item_name="Flour (50kg bag)", quantity=10, unit_cost=Decimal("2.00"))
        self.l_sugar = PurchaseOrderLine.objects.create(
            purchase_order=po, item_name="Sugar", quantity=5, unit_cost=Decimal("4.00"))
        if place:
            place_order(po, self.user)
        return po

    def entry(self, line, qty, cost=None):
        return {"po_line": line, "quantity": qty, "unit_cost": cost or line.unit_cost}


class TotalsTests(PurchasingBase):
    def test_totals_and_numbering(self):
        po = self.make_po(place=False)
        self.assertEqual(po.po_number, "PO-000001")
        self.assertEqual(po.subtotal, Decimal("40.00"))   # 10*2 + 5*4
        self.assertEqual(po.tax_amount, Decimal("4.00"))
        self.assertEqual(po.total, Decimal("49.00"))      # + 5 shipping
        self.assertEqual(po.payment_status, "unpaid")

    def test_item_name_is_free_text_not_tied_to_inventory(self):
        """Purchases (raw materials, services, equipment) aren't resold, so a line's
        item name is just text - no Item model or inventory link involved."""
        po = PurchaseOrder.objects.create(vendor=self.vendor, order_date=date(2026, 1, 1), created_by=self.user)
        line = PurchaseOrderLine.objects.create(
            purchase_order=po, item_name="Oven repair service", quantity=1, unit_cost=Decimal("150.00"))
        self.assertEqual(line.item_name, "Oven repair service")
        self.assertEqual(po.subtotal, Decimal("150.00"))


class ReceivingTests(PurchasingBase):
    def test_partial_then_full_receipt(self):
        po = self.make_po()
        receive_goods(po, date(2026, 1, 5), [self.entry(self.l_flour, 4)], self.user)
        po.refresh_from_db()
        self.assertEqual(po.status, "partial")

        receive_goods(po, date(2026, 1, 6),
                      [self.entry(self.l_flour, 6), self.entry(self.l_sugar, 5)], self.user)
        po.refresh_from_db()
        self.assertEqual(po.status, "received")
        self.assertEqual(po.receipts.count(), 2)
        self.l_flour.refresh_from_db()
        self.assertEqual(self.l_flour.received_qty, 10)

    def test_price_edit_at_receipt_updates_line_total(self):
        po = self.make_po()
        receive_goods(po, date(2026, 1, 5), [self.entry(self.l_flour, 10, cost=Decimal("2.50"))], self.user)
        self.l_flour.refresh_from_db()
        self.assertEqual(self.l_flour.unit_cost, Decimal("2.50"))
        self.assertEqual(po.subtotal, Decimal("45.00"))

    def test_cannot_over_receive_or_receive_nothing_or_receive_draft(self):
        po = self.make_po()
        with self.assertRaises(ValidationError):
            receive_goods(po, date(2026, 1, 5), [self.entry(self.l_flour, 11)], self.user)
        with self.assertRaises(ValidationError):
            receive_goods(po, date(2026, 1, 5), [self.entry(self.l_flour, 0)], self.user)
        draft = self.make_po(place=False)
        with self.assertRaises(ValidationError):
            receive_goods(draft, date(2026, 1, 5), [self.entry(self.l_flour, 1)], self.user)

    def test_close_short(self):
        po = self.make_po()
        receive_goods(po, date(2026, 1, 5), [self.entry(self.l_flour, 3)], self.user)
        close_order(po, self.user)
        po.refresh_from_db()
        self.assertEqual(po.status, "received")
        with self.assertRaises(ValidationError):
            receive_goods(po, date(2026, 1, 6), [self.entry(self.l_flour, 1)], self.user)


class EditingTests(PurchasingBase):
    def test_line_quantity_cannot_drop_below_received(self):
        po = self.make_po()
        receive_goods(po, date(2026, 1, 5), [self.entry(self.l_flour, 6)], self.user)
        self.l_flour.refresh_from_db()
        self.l_flour.quantity = 5
        with self.assertRaises(ValidationError):
            self.l_flour.full_clean()
        with self.assertRaises(ValidationError):
            self.l_flour.delete()

    def test_received_and_cancelled_orders_are_locked(self):
        po = self.make_po()
        receive_goods(po, date(2026, 1, 5),
                      [self.entry(self.l_flour, 10), self.entry(self.l_sugar, 5)], self.user)
        po.refresh_from_db()
        po.notes = "late edit"
        with self.assertRaises(ValidationError):
            po.save()
        with self.assertRaises(ValidationError):
            PurchaseOrderLine.objects.create(purchase_order=po, item_name="Flour", quantity=1, unit_cost=1)

    def test_vendor_locked_after_placing(self):
        po = self.make_po()
        other = Vendor.objects.create(name="Other")
        po.vendor = other
        with self.assertRaises(ValidationError):
            po.save()


class PaymentAndCancelTests(PurchasingBase):
    def test_payments_move_payment_status(self):
        po = self.make_po()   # total 49.00
        record_purchase_payment(po, Decimal("20.00"), "cash", date(2026, 1, 2), self.user)
        self.assertEqual(po.payment_status, "partial")
        self.assertEqual(po.balance_due, Decimal("29.00"))
        record_purchase_payment(po, Decimal("29.00"), "cheque", date(2026, 1, 3), self.user, reference="1042")
        self.assertEqual(po.payment_status, "paid")

    def test_payment_validation(self):
        po = self.make_po()
        with self.assertRaises(ValidationError):
            record_purchase_payment(po, Decimal("49.01"), "cash", date(2026, 1, 2), self.user)
        with self.assertRaises(ValidationError):
            record_purchase_payment(po, Decimal("0"), "cash", date(2026, 1, 2), self.user)
        draft = self.make_po(place=False)
        with self.assertRaises(ValidationError):
            record_purchase_payment(draft, Decimal("1"), "cash", date(2026, 1, 2), self.user)

    def test_cannot_lower_total_below_paid_via_price_edit(self):
        po = self.make_po()
        record_purchase_payment(po, Decimal("49.00"), "cash", date(2026, 1, 2), self.user)
        with self.assertRaises(ValidationError):
            receive_goods(po, date(2026, 1, 5), [self.entry(self.l_flour, 10, cost=Decimal("0.50"))], self.user)
        self.assertEqual(po.receipts.count(), 0)   # whole receipt rolled back

    def test_cancel_rules(self):
        po = self.make_po()
        cancel_order(po, self.user, "changed mind")
        po.refresh_from_db()
        self.assertEqual(po.status, "cancelled")

        paid = self.make_po()
        record_purchase_payment(paid, Decimal("10"), "cash", date(2026, 1, 2), self.user)
        with self.assertRaises(ValidationError):
            cancel_order(paid, self.user, "x")

        received = self.make_po()
        receive_goods(received, date(2026, 1, 5), [self.entry(self.l_flour, 1)], self.user)
        with self.assertRaises(ValidationError):
            cancel_order(received, self.user, "x")

    def test_vendor_outstanding_payable_counts_only_placed_orders(self):
        po = self.make_po()                  # 49.00 placed
        self.make_po(place=False)            # draft, ignored
        record_purchase_payment(po, Decimal("9.00"), "cash", date(2026, 1, 2), self.user)
        self.assertEqual(self.vendor.outstanding_payable(), Decimal("40.00"))


class ViewTests(PurchasingBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def _formset(self, lines, **header):
        data = {
            "vendor": self.vendor.pk, "order_date": "2026-02-01", "tax_percent": "0", "shipping_cost": "0",
            "lines-TOTAL_FORMS": len(lines), "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "1", "lines-MAX_NUM_FORMS": "1000",
        }
        for i, (name, qty, cost) in enumerate(lines):
            data.update({
                f"lines-{i}-item_name": name, f"lines-{i}-quantity": qty, f"lines-{i}-unit_cost": cost,
            })
        data.update(header)
        return data

    def test_create_place_receive_pay_flow_and_audit(self):
        r = self.client.post(reverse("purchasing:create"), self._formset([("Flour (50kg bag)", 10, "1.50")]))
        po = PurchaseOrder.objects.get()
        self.assertRedirects(r, reverse("purchasing:detail", args=[po.pk]))
        self.assertEqual(po.status, "draft")

        self.client.post(reverse("purchasing:place", args=[po.pk]))
        line = po.lines.get()
        r = self.client.post(reverse("purchasing:receive", args=[po.pk]), {
            "received_date": "2026-02-03", "note": "slip 77",
            f"line{line.pk}-quantity": 10, f"line{line.pk}-unit_cost": "1.75",
        })
        self.assertRedirects(r, reverse("purchasing:detail", args=[po.pk]))
        po.refresh_from_db()
        self.assertEqual(po.status, "received")
        self.assertEqual(po.total, Decimal("17.50"))

        self.client.post(reverse("purchasing:payment", args=[po.pk]), {
            "amount": "17.50", "method": "bank_transfer", "payment_date": "2026-02-04", "reference": "TX1",
        })
        self.assertEqual(po.payment_status, "paid")
        actions = set(AuditLog.objects.values_list("action", flat=True))
        self.assertTrue({"po_created", "po_placed", "po_received", "po_payment_recorded"} <= actions)

    def test_receive_form_rejects_over_receipt(self):
        po = self.make_po()
        r = self.client.post(reverse("purchasing:receive", args=[po.pk]), {
            "received_date": "2026-02-03",
            f"line{self.l_flour.pk}-quantity": 99, f"line{self.l_flour.pk}-unit_cost": "2.00",
            f"line{self.l_sugar.pk}-quantity": 0, f"line{self.l_sugar.pk}-unit_cost": "4.00",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(po.receipts.count(), 0)

    def test_pages_render_and_print_gating(self):
        po = self.make_po(place=False)
        for name in ("list", "create"):
            self.assertEqual(self.client.get(reverse(f"purchasing:{name}")).status_code, 200)
        for name in ("detail", "edit"):
            self.assertEqual(self.client.get(reverse(f"purchasing:{name}", args=[po.pk])).status_code, 200)
        r = self.client.get(reverse("purchasing:print", args=[po.pk]))
        self.assertRedirects(r, reverse("purchasing:detail", args=[po.pk]))
        place_order(po, self.user)
        for name in ("print", "receive", "payment", "cancel"):
            self.assertEqual(self.client.get(reverse(f"purchasing:{name}", args=[po.pk])).status_code, 200)
        self.assertContains(self.client.get(reverse("purchasing:print", args=[po.pk])), "Acme Supply")
        self.assertContains(self.client.get(reverse("vendors:detail", args=[self.vendor.pk])), po.po_number)
        csv = self.client.get(reverse("purchasing:list") + "?export=csv").content.decode()
        self.assertIn(po.po_number, csv)

    def test_edit_changes_prices_and_blocks_underpaying(self):
        po = self.make_po()
        record_purchase_payment(po, Decimal("49.00"), "cash", date(2026, 1, 2), self.user)
        data = {
            "vendor": self.vendor.pk, "order_date": "2026-01-01", "tax_percent": "10", "shipping_cost": "5",
            "lines-TOTAL_FORMS": 2, "lines-INITIAL_FORMS": 2, "lines-MIN_NUM_FORMS": 1, "lines-MAX_NUM_FORMS": 1000,
            "lines-0-id": self.l_flour.pk, "lines-0-purchase_order": po.pk,
            "lines-0-item_name": "Flour (50kg bag)", "lines-0-quantity": 10, "lines-0-unit_cost": "1.00",
            "lines-1-id": self.l_sugar.pk, "lines-1-purchase_order": po.pk,
            "lines-1-item_name": "Sugar", "lines-1-quantity": 5, "lines-1-unit_cost": "4.00",
        }
        self.client.post(reverse("purchasing:edit", args=[po.pk]), data)
        self.l_flour.refresh_from_db()
        self.assertEqual(self.l_flour.unit_cost, Decimal("2.00"))   # rejected: total would drop below paid
        data["lines-0-unit_cost"] = "3.00"
        self.client.post(reverse("purchasing:edit", args=[po.pk]), data)
        self.l_flour.refresh_from_db()
        self.assertEqual(self.l_flour.unit_cost, Decimal("3.00"))   # same payload, higher price: accepted
        self.assertIn("po_updated", set(AuditLog.objects.values_list("action", flat=True)))

    def test_item_name_field_has_no_inventory_link_in_the_form(self):
        html = self.client.get(reverse("purchasing:create")).content.decode()
        self.assertNotIn("Linked inventory item", html)
        self.assertNotIn("Not tracked in inventory", html)
