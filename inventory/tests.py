from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from inventory.forms import ItemForm
from inventory.models import Item


def _item_data(**overrides):
    data = {
        "sku": "SP-1", "name": "Lavender Bar", "description": "",
        "cost_price": "2.00", "sale_price": "5.00", "reorder_level": "10",
        "is_active": "on",
    }
    data.update(overrides)
    return data


class ItemFormTests(TestCase):
    def test_item_form_has_no_expiry_fields(self):
        # Expiry lives on production batches only.
        self.assertNotIn("has_expiry", ItemForm().fields)
        self.assertNotIn("expiry_date", ItemForm().fields)

    def test_unticking_active_saves_inactive(self):
        data = _item_data()
        del data["is_active"]
        form = ItemForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.save().is_active)


class ItemActiveTests(TestCase):
    def setUp(self):
        self.active = Item.objects.create(sku="A1", name="Active Bar", cost_price=Decimal("1"), sale_price=Decimal("2"))
        self.inactive = Item.objects.create(sku="I1", name="Retired Bar", cost_price=Decimal("1"),
                                            sale_price=Decimal("2"), is_active=False)

    def test_items_are_active_by_default(self):
        self.assertTrue(self.active.is_active)

    def test_new_invoice_line_only_offers_active_items(self):
        from invoices.forms import InvoiceLineForm
        choices = InvoiceLineForm().fields["item"].queryset
        self.assertIn(self.active, choices)
        self.assertNotIn(self.inactive, choices)

    def test_saved_line_keeps_its_inactive_item(self):
        from invoices.forms import InvoiceLineForm
        from invoices.models import InvoiceLine
        line = InvoiceLine(item=self.inactive, quantity=1, unit_price=Decimal("2"))
        self.assertIn(self.inactive, InvoiceLineForm(instance=line).fields["item"].queryset)

    def test_production_only_offers_active_items(self):
        from production.forms import ProductionBatchForm
        choices = ProductionBatchForm().fields["item"].queryset
        self.assertIn(self.active, choices)
        self.assertNotIn(self.inactive, choices)

    def test_inactive_item_left_off_dashboard_low_stock(self):
        user = User.objects.create_superuser("owner", password="pw12345!x")
        client = Client()
        client.force_login(user)
        response = client.get(reverse("dashboard"))
        names = [item.name for item in response.context["low_stock_items"]]
        self.assertIn("Active Bar", names)
        self.assertNotIn("Retired Bar", names)

    def test_list_and_detail_show_status(self):
        user = User.objects.create_superuser("owner", password="pw12345!x")
        client = Client()
        client.force_login(user)
        self.assertContains(client.get(reverse("inventory:list")), "Inactive")
        self.assertContains(client.get(reverse("inventory:detail", args=[self.inactive.pk])), "Inactive")
