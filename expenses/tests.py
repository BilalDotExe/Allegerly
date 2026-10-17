from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.permissions import GROUP_ADMIN
from expenses.forms import OTHER_CATEGORY, ExpenseLineFormSet, group_line_forms
from expenses.models import ExpenseLine, ExpenseReport


def line_post(index, description='', category='', amount='', reference='', pk=''):
    return {
        f'lines-{index}-description': description,
        f'lines-{index}-category': category,
        f'lines-{index}-amount': amount,
        f'lines-{index}-reference': reference,
        f'lines-{index}-id': pk,
    }


def formset_post(count, initial=0):
    data = {
        'lines-TOTAL_FORMS': str(count),
        'lines-INITIAL_FORMS': str(initial),
        'lines-MIN_NUM_FORMS': '0',
        'lines-MAX_NUM_FORMS': '1000',
    }
    return data


class ExpenseReportModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('exp_u', password='test-pass-123')

    def make_report(self, name='October supplies'):
        return ExpenseReport.objects.create(
            name=name, report_date=timezone.localdate(), created_by=self.user
        )

    def test_report_number_is_sequential(self):
        self.assertEqual(self.make_report().report_number, 'EXP-000001')
        self.assertEqual(self.make_report('Second').report_number, 'EXP-000002')

    def test_total_is_zero_without_lines(self):
        self.assertEqual(self.make_report().total, Decimal('0.00'))

    def test_total_sums_lines(self):
        report = self.make_report()
        ExpenseLine.objects.create(report=report, description='Bags', amount=Decimal('10.50'))
        ExpenseLine.objects.create(report=report, description='Tape', amount=Decimal('2.25'))
        self.assertEqual(report.total, Decimal('12.75'))

    def test_cannot_be_deleted(self):
        report = self.make_report()
        with self.assertRaises(ValidationError):
            report.delete()

    def test_report_number_cannot_change(self):
        report = self.make_report()
        report.report_number = 'EXP-999999'
        with self.assertRaises(ValidationError):
            report.save()

    def test_title_and_notes_stay_editable(self):
        report = self.make_report()
        report.name = 'Renamed'
        report.notes = 'Checked against receipts'
        report.save()
        report.refresh_from_db()
        self.assertEqual(report.name, 'Renamed')

    def test_grouped_lines_buckets_by_category_case_insensitively(self):
        report = self.make_report()
        ExpenseLine.objects.create(report=report, description='Bags', category='Packaging', amount=Decimal('5.00'))
        ExpenseLine.objects.create(report=report, description='Van fuel', category='Transport', amount=Decimal('20.00'))
        ExpenseLine.objects.create(report=report, description='Tape', category='packaging', amount=Decimal('1.00'))

        groups = report.grouped_lines
        self.assertEqual([g['category'] for g in groups], ['Packaging', 'Transport'])
        self.assertEqual(groups[0]['total'], Decimal('6.00'))
        # line_no restarts inside each category
        self.assertEqual([line.line_no for line in groups[0]['lines']], [1, 2])
        self.assertEqual([line.line_no for line in groups[1]['lines']], [1])

    def test_line_strips_category_and_rounds_amount(self):
        report = self.make_report()
        line = ExpenseLine.objects.create(
            report=report, description='Bags', category='  Packaging  ', amount=Decimal('1.005')
        )
        line.refresh_from_db()
        self.assertEqual(line.category, 'Packaging')
        self.assertEqual(line.amount, Decimal('1.01'))


class GroupLineFormsTests(TestCase):
    """The accordion grouping drives the entry form, so test it directly."""

    def build(self, categories):
        data = formset_post(len(categories))
        for index, category in enumerate(categories):
            data.update(line_post(index, description=f'Thing {index}', category=category, amount='1.00'))
        formset = ExpenseLineFormSet(data)
        self.assertTrue(formset.is_valid(), formset.errors)
        return formset

    def test_known_category_is_selected_in_dropdown(self):
        groups = group_line_forms(self.build(['Packaging']), ['Packaging', 'Transport'])
        self.assertEqual(groups[0]['selected'], 'Packaging')
        self.assertEqual(groups[0]['custom'], '')

    def test_unknown_category_falls_back_to_other(self):
        groups = group_line_forms(self.build(['Licences']), ['Packaging'])
        self.assertEqual(groups[0]['selected'], OTHER_CATEGORY)
        self.assertEqual(groups[0]['custom'], 'Licences')

    def test_rows_sharing_a_category_land_in_one_group(self):
        groups = group_line_forms(self.build(['Packaging', 'packaging']), ['Packaging'])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['forms']), 2)

    def test_exactly_one_group_is_open(self):
        groups = group_line_forms(self.build(['Packaging', 'Transport']), ['Packaging', 'Transport'])
        self.assertEqual([g['open'] for g in groups], [True, False])


class ExpenseViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('admin_u', password='test-pass-123')
        self.user.groups.add(Group.objects.get(name=GROUP_ADMIN))
        self.client.force_login(self.user)

    def test_list_renders_when_empty(self):
        response = self.client.get(reverse('expenses:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No expense reports found')

    def test_create_page_renders(self):
        response = self.client.get(reverse('expenses:create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a category')

    def test_create_saves_report_with_lines(self):
        data = {
            'name': 'October supplies',
            'report_date': '2026-10-01',
            'notes': '',
        }
        data.update(formset_post(2))
        data.update(line_post(0, description='Bags', category='Packaging', amount='10.00'))
        data.update(line_post(1, description='Van fuel', category='Transport', amount='20.50'))

        response = self.client.post(reverse('expenses:create'), data)

        report = ExpenseReport.objects.get()
        self.assertRedirects(response, reverse('expenses:detail', args=[report.pk]))
        self.assertEqual(report.report_number, 'EXP-000001')
        self.assertEqual(report.created_by, self.user)
        self.assertEqual(report.total, Decimal('30.50'))
        self.assertEqual(report.lines.count(), 2)

    def test_blank_amount_saves_as_zero(self):
        """OptionalWithDefaultMixin: a row needs only a description."""
        data = {'name': 'Odds and ends', 'report_date': '2026-10-01', 'notes': ''}
        data.update(formset_post(1))
        data.update(line_post(0, description='Unpriced item', category='Supplies'))

        self.client.post(reverse('expenses:create'), data)

        line = ExpenseLine.objects.get()
        self.assertEqual(line.amount, Decimal('0.00'))

    def test_empty_rows_are_ignored(self):
        data = {'name': 'Just one thing', 'report_date': '2026-10-01', 'notes': ''}
        data.update(formset_post(3))
        data.update(line_post(0, description='Bags', category='Packaging', amount='5.00'))
        # The page pre-fills the hidden category on every row, including blank ones.
        data.update(line_post(1, category='Packaging'))
        data.update(line_post(2, category='Transport'))

        self.client.post(reverse('expenses:create'), data)

        self.assertEqual(ExpenseLine.objects.count(), 1)

    def test_blank_date_defaults_to_today(self):
        data = {'name': 'No date given', 'report_date': '', 'notes': ''}
        data.update(formset_post(1))
        data.update(line_post(0, description='Bags', category='Packaging', amount='1.00'))

        self.client.post(reverse('expenses:create'), data)

        self.assertEqual(ExpenseReport.objects.get().report_date, timezone.localdate())

    def test_detail_renders_grouped_lines(self):
        report = ExpenseReport.objects.create(
            name='October supplies', report_date=timezone.localdate(), created_by=self.user
        )
        ExpenseLine.objects.create(report=report, description='Bags', category='Packaging', amount=Decimal('5.00'))

        response = self.client.get(reverse('expenses:detail', args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Packaging')
        self.assertContains(response, 'Bags')

    def test_edit_updates_title_and_lines(self):
        report = ExpenseReport.objects.create(
            name='Original', report_date=timezone.localdate(), created_by=self.user
        )
        line = ExpenseLine.objects.create(
            report=report, description='Bags', category='Packaging', amount=Decimal('5.00')
        )

        data = {'name': 'Corrected', 'report_date': '2026-10-02', 'notes': 'Fixed'}
        data.update(formset_post(1, initial=1))
        data.update(line_post(0, description='Bags', category='Packaging', amount='7.50', pk=str(line.pk)))

        response = self.client.post(reverse('expenses:edit', args=[report.pk]), data)

        self.assertRedirects(response, reverse('expenses:detail', args=[report.pk]))
        report.refresh_from_db()
        self.assertEqual(report.name, 'Corrected')
        self.assertEqual(report.total, Decimal('7.50'))
        # The number is still the one it was issued
        self.assertEqual(report.report_number, 'EXP-000001')

    def test_csv_export(self):
        ExpenseReport.objects.create(
            name='October supplies', report_date=timezone.localdate(), created_by=self.user
        )
        response = self.client.get(reverse('expenses:list'), {'export': 'csv'})
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('EXP-000001', response.content.decode())

    def test_date_filter_narrows_the_list(self):
        ExpenseReport.objects.create(name='Old', report_date='2026-01-05', created_by=self.user)
        ExpenseReport.objects.create(name='New', report_date='2026-10-05', created_by=self.user)

        response = self.client.get(reverse('expenses:list'), {'start_date': '2026-06-01'})
        self.assertContains(response, 'New')
        self.assertNotContains(response, '>Old<')
