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
            "name": "Shop run", "report_date": timezone.localdate().isoformat(), "notes": "",
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

    def test_only_the_date_is_required_and_a_blank_name_comes_from_it(self):
        r = self.post_report([("Cleaning cloths", "Anything I like", "")], name="", report_date="2026-11-03")
        report = ExpenseReport.objects.get()
        self.assertRedirects(r, reverse("expenses:detail", args=[report.pk]))
        self.assertEqual(report.name, "Expense Nov 3, 2026")
        line = report.lines.get()
        self.assertEqual((line.amount, line.category), (Decimal("0.00"), "Anything I like"))

    def test_report_can_be_saved_with_no_lines_but_needs_a_date(self):
        self.post_report([("", "", "")], report_date="2026-11-03")
        self.assertEqual(ExpenseReport.objects.get().lines.count(), 0)
        r = self.post_report([], report_date="")
        self.assertContains(r, "This field is required")
        self.assertEqual(ExpenseReport.objects.count(), 1)

    def test_a_typed_name_is_kept_and_clearing_it_on_edit_falls_back_to_the_date(self):
        report = self.make_report(name="  Market day  ")
        self.assertEqual(report.name, "Market day")
        report.name = ""
        report.save()
        self.assertEqual(report.name, "Expense Oct 1, 2026")

    def test_a_line_needs_nothing_but_something_typed(self):
        self.post_report([("", "Rent", "50")], name="Amount only")
        line = ExpenseReport.objects.get(name="Amount only").lines.get()
        self.assertEqual((line.description, line.category, line.amount), ("", "Rent", Decimal("50.00")))

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

    def test_a_row_with_only_a_category_is_skipped(self):
        self.post_report([("", "Rent", "")])
        self.assertEqual(ExpenseReport.objects.get().lines.count(), 0)

    def test_category_totals_merge_spellings(self):
        report = self.make_report(lines=[("A", "Rent", "1"), ("B", "rent", "2"), ("C", "Supplies", "3")])
        totals = report.category_totals()
        self.assertEqual([row["category"] for row in totals], ["Rent", "Supplies"])
        self.assertEqual([(row["count"], row["total"]) for row in totals], [(2, Decimal("3.00")), (1, Decimal("3.00"))])

    def test_form_suggests_categories_and_has_line_controls(self):
        report = self.make_report(lines=[("A", "Rent", "1"), ("B", "Custom thing", "2")])
        create = self.client.get(reverse("expenses:create"))
        self.assertContains(create, '<datalist id="expense-category-options">')
        self.assertContains(create, '<option value="Custom thing">')   # typed before, now suggested
        self.assertContains(create, '<option value="Utilities">')      # starter list
        self.assertContains(create, 'list="expense-category-options"')
        self.assertContains(create, 'id="add-line"')
        self.assertContains(create, 'id="remove-line-dialog"')        # removal is confirmed first
        edit = self.client.get(reverse("expenses:edit", args=[report.pk]))
        page = edit.content.decode().split("<template")[0]   # the rows the server drew
        self.assertEqual(page.count('class="line-del-btn"'), 2)
        self.assertIn('data-label="Line">2</td>', page)               # one running line number

    def test_a_typed_new_category_is_saved_as_typed(self):
        self.post_report([("Stall fee", "Farmers market", "35")])
        self.assertEqual(ExpenseLine.objects.get().category, "Farmers market")

    def test_edit_can_remove_a_line(self):
        report = self.make_report(lines=[("Keep", "Rent", "10"), ("Drop", "Rent", "5")])
        keep, drop = report.lines.all()
        data = {"name": report.name, "report_date": "2026-10-01", "notes": "",
                "lines-TOTAL_FORMS": 2, "lines-INITIAL_FORMS": 2, "lines-MIN_NUM_FORMS": 0, "lines-MAX_NUM_FORMS": 1000}
        for i, line in enumerate((keep, drop)):
            data.update({f"lines-{i}-id": line.pk, f"lines-{i}-report": report.pk, f"lines-{i}-description": line.description,
                         f"lines-{i}-category": line.category, f"lines-{i}-amount": str(line.amount)})
        data["lines-1-DELETE"] = "on"
        self.client.post(reverse("expenses:edit", args=[report.pk]), data)
        self.assertEqual(list(report.lines.values_list("description", flat=True)), ["Keep"])
        self.assertEqual(report.total, Decimal("10.00"))

    def test_pages_render_with_line_numbers(self):
        report = self.make_report(lines=[("A", "Rent", "1"), ("B", "Rent", "2"), ("C", "Supplies", "3")])
        detail = self.client.get(reverse("expenses:detail", args=[report.pk]))
        self.assertContains(detail, '<td class="col-line">3</td>', count=1)
        self.assertContains(detail, "By category")
        listing = self.client.get(reverse("expenses:list"))
        self.assertContains(listing, '<td class="col-line">3</td>', count=1)
        self.assertContains(listing, "> New Expense</a>")
        self.assertIn(report.report_number, self.client.get(reverse("expenses:list") + "?export=csv").content.decode())

    def test_in_the_sidebar_for_staff_not_employees(self):
        self.assertContains(self.client.get(reverse("dashboard")), f'href="{reverse("expenses:list")}"')

    def test_employees_cannot_reach_expenses(self):
        employee = User.objects.create_user("emp", password="pw")
        employee.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        self.client.force_login(employee)
        self.assertEqual(self.client.get(reverse("expenses:list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports:expenses")).status_code, 403)
        self.assertNotContains(self.client.get(reverse("dashboard")), f'href="{reverse("expenses:list")}"')


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
        self.assertIn(",2,,B,", csv)   # line 2, no category, description B (same column order as the form)

    def test_listed_on_the_reports_index(self):
        self.assertContains(self.client.get(reverse("reports:index")), reverse("reports:expenses"))
        self.assertContains(self.client.get(reverse("reports:expenses")), "Expenses Report")


class ExpenseDashboardTests(ExpenseBase):
    def test_kpi_cash_flow_and_category_chart_include_expenses(self):
        from core.dashboard_data import build_dashboard

        today = timezone.localdate()
        self.make_report(when=today, lines=[("Power", "Utilities", "40"), ("Rent", "Rent", "100"), ("Bulbs", "utilities", "5")])
        self.make_report(when=today + timedelta(days=40), lines=[("Not spent yet", "Rent", "999")])
        data = build_dashboard(6, today)
        kpi = {k["label"]: k for k in data["kpis"]}["Expenses this month"]
        self.assertEqual(kpi["value"], "$145.00")
        self.assertFalse(kpi["good_up"])   # spending more is not "good"
        this_month = data["cash_chart"]["cols"][-1]
        self.assertIn(("Expenses", "$145.00"), [(b["label"], b["value"]) for b in this_month["bars"]])
        chart = data["expense_chart"]
        self.assertEqual([s["label"] for s in chart["legend"]], ["Rent", "Utilities"])   # biggest first, spellings merged
        self.assertEqual(chart["cols"][-1]["total"], "$145.00")
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, "Expenses this month")
        self.assertContains(page, f'href="{reverse("expenses:list")}"')

    def test_beyond_four_categories_the_rest_are_other(self):
        from core.dashboard_data import build_dashboard

        today = timezone.localdate()
        self.make_report(when=today, lines=[(c, c, str(10 - i)) for i, c in enumerate("ABCDEF")])
        legend = [s["label"] for s in build_dashboard(6, today)["expense_chart"]["legend"]]
        self.assertEqual(legend, ["A", "B", "C", "D", "Other"])
