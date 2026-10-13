from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditLog
from core.permissions import GROUP_EMPLOYEE
from .models import ExpenseLine, ExpenseReport


class ExpenseBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("boss", "b@x.com", "pw")
        self.client.force_login(self.user)

    def make_report(self, name="October supplies", when=date(2026, 10, 1), lines=()):
        report = ExpenseReport.objects.create(name=name, report_date=when, created_by=self.user)
        for description, category, amount in lines:
            ExpenseLine.objects.create(report=report, description=description, category=category, amount=amount)
        return report

    def post_report(self, lines, **header):
        data = {
            "name": "Shop run", "report_date": "", "notes": "",
            "lines-TOTAL_FORMS": len(lines), "lines-INITIAL_FORMS": 0,
            "lines-MIN_NUM_FORMS": 0, "lines-MAX_NUM_FORMS": 1000,
        }
        for i, (description, category, amount) in enumerate(lines):
            data.update({
                f"lines-{i}-description": description, f"lines-{i}-category": category,
                f"lines-{i}-amount": amount,
            })
        data.update(header)
        return self.client.post(reverse("expenses:create"), data)


class ExpenseReportTests(ExpenseBase):
    def test_numbering_and_total(self):
        report = self.make_report(lines=[("Soap base", "Supplies", "12.50"), ("Taxi", "Transport", "7.25")])
        self.assertEqual(report.report_number, "EXP-000001")
        self.assertEqual(report.total, Decimal("19.75"))
        self.assertEqual(self.make_report(name="Second").report_number, "EXP-000002")

    def test_only_the_name_is_required_and_blank_date_and_amount_default(self):
        r = self.post_report([("Cleaning cloths", "Anything I like", "")])
        report = ExpenseReport.objects.get()
        self.assertRedirects(r, reverse("expenses:detail", args=[report.pk]))
        self.assertEqual(report.report_date, timezone.localdate())
        line = report.lines.get()
        self.assertEqual((line.amount, line.category), (Decimal("0.00"), "Anything I like"))

    def test_report_can_be_saved_with_no_lines_but_needs_a_name(self):
        self.post_report([("", "", "")])
        self.assertEqual(ExpenseReport.objects.get().lines.count(), 0)
        self.post_report([], name="")
        self.assertEqual(ExpenseReport.objects.count(), 1)

    def test_a_line_with_an_amount_needs_a_description(self):
        self.post_report([("", "Rent", "50")], name="Bad")
        self.assertFalse(ExpenseReport.objects.filter(name="Bad").exists())

    def test_cannot_be_deleted(self):
        with self.assertRaises(ValidationError):
            self.make_report().delete()

    def test_edit_updates_lines_and_is_audited(self):
        report = self.make_report(lines=[("Soap base", "Supplies", "10.00")])
        line = report.lines.get()
        self.client.post(reverse("expenses:edit", args=[report.pk]), {
            "name": "October supplies", "report_date": "2026-10-01", "notes": "",
            "lines-TOTAL_FORMS": 1, "lines-INITIAL_FORMS": 1, "lines-MIN_NUM_FORMS": 0, "lines-MAX_NUM_FORMS": 1000,
            "lines-0-id": line.pk, "lines-0-report": report.pk,
            "lines-0-description": "Soap base", "lines-0-category": "Supplies", "lines-0-amount": "15.00",
        })
        self.assertEqual(report.total, Decimal("15.00"))
        self.assertIn("expense_report_updated", set(AuditLog.objects.values_list("action", flat=True)))

    def test_category_with_no_text_in_its_rows_is_skipped(self):
        self.post_report([("", "Rent", "")])
        self.assertEqual(ExpenseReport.objects.get().lines.count(), 0)

    def test_grouping_numbers_lines_per_category(self):
        report = self.make_report(lines=[("A", "Rent", "1"), ("B", "rent", "2"), ("C", "Supplies", "3")])
        groups = report.grouped_lines()
        self.assertEqual([g["category"] for g in groups], ["Rent", "Supplies"])
        self.assertEqual([line.line_no for line in groups[0]["lines"]], [1, 2])
        self.assertEqual((groups[0]["total"], groups[1]["total"]), (Decimal("3.00"), Decimal("3.00")))

    def test_form_is_a_category_accordion_with_a_dropdown(self):
        report = self.make_report(lines=[("A", "Rent", "1"), ("B", "Custom thing", "2")])
        create = self.client.get(reverse("expenses:create"))
        self.assertContains(create, 'id="add-category"')
        self.assertContains(create, '<option value="Custom thing">')
        self.assertNotContains(create, "expense-categories")
        edit = self.client.get(reverse("expenses:edit", args=[report.pk]))
        page = edit.content.decode().split("<template")[0]   # the sections the server drew
        self.assertEqual(page.count('class="exp-cat is-open"'), 1)   # only one open
        self.assertEqual(page.count('class="exp-cat"'), 1)
        self.assertEqual(page.count('class="line-no">1</td>'), 2)   # numbering restarts per category

    def test_a_category_not_in_the_dropdown_comes_back_as_other(self):
        r = self.post_report([("", "Brand new thing", "5")], name="Bad")
        self.assertContains(r, "This field is required")
        self.assertContains(r, 'value="Brand new thing"')
        self.assertContains(r, '<option value="__other__" selected>')

    def test_pages_render_grouped_with_line_numbers(self):
        report = self.make_report(lines=[("A", "Rent", "1"), ("B", "Rent", "2"), ("C", "Supplies", "3")])
        detail = self.client.get(reverse("expenses:detail", args=[report.pk]))
        self.assertContains(detail, '<td class="col-line">2</td>', count=1)
        self.assertContains(detail, "subtotal $3.00", count=2)   # Rent 1+2, Supplies 3
        listing = self.client.get(reverse("expenses:list"))
        self.assertContains(listing, '<td class="col-line">2</td>', count=1)
        self.assertContains(listing, "> New Expense</a>")
        self.assertIn(report.report_number, self.client.get(reverse("expenses:list") + "?export=csv").content.decode())

    def test_employees_cannot_reach_expenses(self):
        employee = User.objects.create_user("emp", password="pw")
        employee.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        self.client.force_login(employee)
        self.assertEqual(self.client.get(reverse("expenses:list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports:expenses")).status_code, 403)


class ExpensesReportTests(ExpenseBase):
    def test_defaults_to_beginning_through_today_and_groups_by_category(self):
        today = timezone.localdate()
        self.make_report(name="Old", when=date(2025, 1, 5), lines=[("Rent", "Rent", "100"), ("Bags", "supplies", "20")])
        self.make_report(name="Recent", when=today, lines=[("Boxes", "Supplies", "30")])
        self.make_report(name="Future", when=today + timedelta(days=30), lines=[("Later", "Rent", "999")])
        r = self.client.get(reverse("reports:expenses"))
        self.assertEqual(r.context["total"], Decimal("150.00"))
        self.assertEqual(r.context["period_start"], date(2025, 1, 5))
        self.assertEqual(r.context["period_end"], today)
        by_label = {row["label"].lower(): row for row in r.context["categories"]}
        self.assertEqual(by_label["supplies"]["total"], Decimal("50.00"))   # "supplies"/"Supplies" merge
        self.assertEqual(by_label["supplies"]["count"], 2)
        self.assertEqual(r.context["categories"][0]["label"].lower(), "rent")   # largest first

    def test_date_filter_and_csv_export_with_line_numbers(self):
        self.make_report(name="Old", when=date(2025, 1, 5), lines=[("Rent", "Rent", "100")])
        self.make_report(name="New", when=date(2026, 2, 1), lines=[("A", "", "1"), ("B", "", "2")])
        r = self.client.get(reverse("reports:expenses"), {"start_date": "2026-01-01"})
        self.assertEqual(r.context["total"], Decimal("3.00"))
        csv = self.client.get(reverse("reports:expenses") + "?export=csv").content.decode()
        self.assertIn("Line", csv.splitlines()[0])
        self.assertIn(",2,B,", csv)

    def test_listed_on_the_reports_index(self):
        self.assertContains(self.client.get(reverse("reports:index")), reverse("reports:expenses"))
        self.assertContains(self.client.get(reverse("reports:expenses")), "Expenses Report")
