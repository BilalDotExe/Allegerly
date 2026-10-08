from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from core.money import money, zero_money
from core.permissions import (
    GROUP_ADMIN,
    GROUP_EMPLOYEE,
    GROUP_STAFF,
    GROUP_VIEW_ONLY,
    can_view,
    is_admin,
    is_employee,
    is_staff_user,
)
from core.utils import generate_temp_password


class MoneyHelperTests(TestCase):
    def test_rounds_half_up_to_two_places(self):
        self.assertEqual(money('1.005'), Decimal('1.01'))
        self.assertEqual(money(Decimal('1.004')), Decimal('1.00'))

    def test_zero_money(self):
        self.assertEqual(zero_money(), Decimal('0.00'))


class PermissionGroupMigrationTests(TestCase):
    def test_three_groups_exist(self):
        names = set(Group.objects.values_list('name', flat=True))
        self.assertTrue({GROUP_ADMIN, GROUP_STAFF, GROUP_VIEW_ONLY}.issubset(names))


class PermissionHelperTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user('admin_u', password='test-pass-123')
        self.staff_user = User.objects.create_user('staff_u', password='test-pass-123')
        self.view_user = User.objects.create_user('view_u', password='test-pass-123')
        self.nobody = User.objects.create_user('nobody', password='test-pass-123')

        self.admin_user.groups.add(Group.objects.get(name=GROUP_ADMIN))
        self.staff_user.groups.add(Group.objects.get(name=GROUP_STAFF))
        self.view_user.groups.add(Group.objects.get(name=GROUP_VIEW_ONLY))

    def test_admin_flags(self):
        self.assertTrue(is_admin(self.admin_user))
        self.assertFalse(is_admin(self.staff_user))

    def test_staff_flags(self):
        self.assertTrue(is_staff_user(self.admin_user))
        self.assertTrue(is_staff_user(self.staff_user))
        self.assertFalse(is_staff_user(self.view_user))

    def test_can_view(self):
        self.assertTrue(can_view(self.view_user))
        self.assertFalse(can_view(self.nobody))


class AuthViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('worker', password='test-pass-123')
        self.user.groups.add(Group.objects.get(name=GROUP_STAFF))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_dashboard_forbidden_without_group(self):
        lone = User.objects.create_user('lone', password='test-pass-123')
        # force_login bypasses AxesStandaloneBackend, which needs a real request
        self.client.force_login(lone)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_ok_for_grouped_user(self):
        # force_login bypasses AxesStandaloneBackend, which needs a real request
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)


class AdminSitePermissionTests(TestCase):
    """Django admin must use the Admin group, not is_staff."""

    def setUp(self):
        self.client = Client()
        password = 'test-pass-123'

        self.admin_user = User.objects.create_user('admin_u', password=password)
        self.admin_user.groups.add(Group.objects.get(name=GROUP_ADMIN))

        # is_staff=True on Staff must still be denied — that was the old gate.
        self.staff_user = User.objects.create_user(
            'staff_u', password=password, is_staff=True
        )
        self.staff_user.groups.add(Group.objects.get(name=GROUP_STAFF))

        self.view_user = User.objects.create_user('view_u', password=password)
        self.view_user.groups.add(Group.objects.get(name=GROUP_VIEW_ONLY))

    def test_anonymous_is_sent_to_admin_login(self):
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.url)

    def test_staff_forbidden_even_if_is_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 403)

    def test_view_only_forbidden(self):
        self.client.force_login(self.view_user)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 403)

    def test_admin_group_allowed_without_is_staff(self):
        self.assertFalse(self.admin_user.is_staff)
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)


class DashboardChartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('chartuser', password='pw12345!x')
        self.client = Client()
        self.client.force_login(self.user)

    def test_dashboard_renders_with_empty_database(self):
        for value in ('', '3', '12', 'junk'):
            response = self.client.get(reverse('dashboard'), {'range': value})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Outstanding invoices')

    def test_dashboard_reflects_issued_invoice_and_payment(self):
        from datetime import timedelta
        from django.utils import timezone
        from customers.models import Customer
        from inventory.models import Item
        from invoices.models import Invoice, InvoiceLine, Payment
        from core.dashboard_data import build_dashboard

        customer = Customer.objects.create(first_name='Acme')
        item = Item.objects.create(sku='S1', name='Soap', cost_price=Decimal('2'), sale_price=Decimal('5'))
        today = timezone.localdate()
        invoice = Invoice.objects.create(customer=customer, created_by=self.user)
        InvoiceLine.objects.create(invoice=invoice, item=item, quantity=10, unit_price=Decimal('5.00'))
        invoice.status = 'issued'
        invoice.issue_date = today - timedelta(days=45)
        invoice.due_date = today - timedelta(days=40)
        invoice.save()
        Payment.objects.create(invoice=invoice, amount=Decimal('20.00'), method='cash',
                               payment_date=today, created_by=self.user)

        data = build_dashboard(6, today)
        kpis = {k['label']: k['value'] for k in data['kpis']}
        self.assertEqual(kpis['Outstanding'], '$30.00')
        self.assertEqual(kpis['Overdue'], '$30.00')
        self.assertEqual(kpis['Cash received'], '$20.00')
        ageing = {b['label']: b['value'] for b in data['ageing_bars']}
        self.assertEqual(ageing['31–60 days'], Decimal('30.00'))
        self.assertEqual(data['top_customers'][0]['label'], 'Acme')
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)


class ChartHelperTests(TestCase):
    def test_nice_max_and_empty_sparkline(self):
        from core.charts import nice_max, sparkline, delta
        self.assertEqual(nice_max(0), 1.0)
        self.assertEqual(nice_max(730), 1000)
        self.assertIsNone(sparkline([0, 0, 0]))
        self.assertIsNone(delta(5, 0))


from core.utils import format_us_phone


class UsPhoneFormatTests(TestCase):
    def test_ten_digits(self):
        self.assertEqual(format_us_phone("2132915566"), "(213) 291-5566")

    def test_formatted_input_reformats_cleanly(self):
        self.assertEqual(format_us_phone("(213) 291-5566"), "(213) 291-5566")
        self.assertEqual(format_us_phone("213-291-5566"), "(213) 291-5566")

    def test_leading_country_code_dropped(self):
        self.assertEqual(format_us_phone("12132915566"), "(213) 291-5566")
        self.assertEqual(format_us_phone("+1 213 291 5566"), "(213) 291-5566")

    def test_non_us_length_passed_through_unchanged(self):
        self.assertEqual(format_us_phone("12345"), "12345")
        self.assertEqual(format_us_phone("2132915566 ext 2"), "2132915566 ext 2")

    def test_blank_passed_through(self):
        self.assertEqual(format_us_phone(""), "")
        self.assertIsNone(format_us_phone(None))


class GenerateTempPasswordTests(TestCase):
    def test_eight_chars_mixed_case_and_digit(self):
        password = generate_temp_password()
        self.assertEqual(len(password), 8)
        self.assertTrue(any(c.isupper() for c in password))
        self.assertTrue(any(c.islower() for c in password))
        self.assertTrue(any(c.isdigit() for c in password))
        self.assertFalse(password.isdigit())  # NumericPasswordValidator would reject this

    def test_custom_length(self):
        self.assertEqual(len(generate_temp_password(12)), 12)

    def test_passwords_are_not_repeated(self):
        passwords = {generate_temp_password() for _ in range(25)}
        self.assertGreater(len(passwords), 20)


class EmployeeGroupTests(TestCase):
    def test_employee_group_exists(self):
        self.assertTrue(Group.objects.filter(name=GROUP_EMPLOYEE).exists())


class IsEmployeeHelperTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user('helper_emp', password='test-pass-123')
        self.employee.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        self.superuser = User.objects.create_superuser('helper_super', password='test-pass-123')
        self.admin_user = User.objects.create_user('helper_admin', password='test-pass-123')
        self.admin_user.groups.add(Group.objects.get(name=GROUP_ADMIN))

    def test_employee_group_member_is_employee(self):
        self.assertTrue(is_employee(self.employee))

    def test_superuser_is_never_employee(self):
        # Must stay False: this flag swaps in the trimmed dashboard/sidebar,
        # and the account owner's own superuser login must never see those.
        self.assertFalse(is_employee(self.superuser))

    def test_other_groups_are_not_employee(self):
        self.assertFalse(is_employee(self.admin_user))

    def test_anonymous_is_not_employee(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(is_employee(AnonymousUser()))


class EmployeeAccessRestrictionTests(TestCase):
    """Employee accounts: invoices/purchasing/returns/damages yes, everything else no."""

    def setUp(self):
        self.client = Client()
        self.employee = User.objects.create_user('restricted_emp', password='test-pass-123')
        self.employee.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        self.client.force_login(self.employee)

    def test_allowed_areas(self):
        for name in (
            'invoices:list', 'invoices:create', 'purchasing:list', 'purchasing:create',
            'returns:list', 'returns:create', 'damages:list', 'damages:create',
            'invoices:credit_list',
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f'{name} should be reachable by Employee')

    def test_restricted_areas(self):
        for name in (
            'customers:list', 'customers:create', 'vendors:list', 'vendors:create',
            'inventory:list', 'inventory:create', 'inventory:movements',
            'inventory:expiry_list', 'production:list', 'production:create',
            'reports:index', 'reports:sales',
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 403, f'{name} should be forbidden for Employee')

    def test_employee_dashboard_is_trimmed(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/dashboard_employee.html')
        self.assertContains(response, 'Quick links')

    def test_sidebar_hides_restricted_links(self):
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Customers</a>')
        self.assertNotContains(response, 'Items</a>')
        # ">Reports</a>" (not just "Reports</a>") so this doesn't false-match
        # the still-allowed "Damage Reports" link, which also ends in "Reports".
        self.assertNotContains(response, '>Reports</a>')
        self.assertContains(response, 'Invoices</a>')
        self.assertContains(response, 'Purchase Orders</a>')
        self.assertContains(response, 'Returns</a>')
        self.assertContains(response, 'Damage Reports</a>')

    def test_cannot_reach_employee_management(self):
        self.assertEqual(self.client.get(reverse('employee_list')).status_code, 403)

    def test_cannot_reach_company_settings(self):
        self.assertEqual(self.client.get(reverse('account_settings')).status_code, 403)


class EmployeeManagementViewTests(TestCase):
    """Creating/deleting employees and resetting passwords is superuser-only —
    Admin-group membership alone is not enough."""

    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser('mgmt_boss', password='test-pass-123')
        self.admin_user = User.objects.create_user('mgmt_admin', password='test-pass-123')
        self.admin_user.groups.add(Group.objects.get(name=GROUP_ADMIN))

    def test_admin_group_cannot_manage_employees(self):
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get(reverse('employee_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('employee_create')).status_code, 403)

    def test_superuser_can_create_employee_with_manual_password(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('employee_create'), {
            'username': 'newhire', 'first_name': 'New', 'last_name': 'Hire',
            'password': 'Sup3rSecret!42',
        })
        self.assertRedirects(response, reverse('employee_list'))
        employee = User.objects.get(username='newhire')
        self.assertTrue(employee.groups.filter(name=GROUP_EMPLOYEE).exists())
        self.assertTrue(employee.check_password('Sup3rSecret!42'))
        self.assertFalse(employee.is_superuser)
        self.assertFalse(employee.is_staff)

    def test_blank_password_autogenerates_eight_chars(self):
        self.client.force_login(self.superuser)
        self.client.post(reverse('employee_create'), {
            'username': 'autogen', 'first_name': '', 'last_name': '', 'password': '',
        })
        employee = User.objects.get(username='autogen')
        revealed = self.client.session['reveal_password']
        self.assertEqual(revealed['user_id'], employee.pk)
        self.assertEqual(len(revealed['password']), 8)
        self.assertTrue(employee.check_password(revealed['password']))

    def test_password_is_shown_once_then_cleared(self):
        self.client.force_login(self.superuser)
        self.client.post(reverse('employee_create'), {
            'username': 'onceonly', 'first_name': '', 'last_name': '', 'password': '',
        })
        first_view = self.client.get(reverse('employee_list'))
        self.assertContains(first_view, 'Password for onceonly')
        second_view = self.client.get(reverse('employee_list'))
        self.assertNotContains(second_view, 'Password for onceonly')

    def test_duplicate_username_rejected(self):
        self.client.force_login(self.superuser)
        User.objects.create_user('taken', password='test-pass-123')
        response = self.client.post(reverse('employee_create'), {
            'username': 'taken', 'first_name': '', 'last_name': '', 'password': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='taken', groups__name=GROUP_EMPLOYEE).exists())

    def test_weak_password_rejected(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('employee_create'), {
            'username': 'weakpw', 'first_name': '', 'last_name': '', 'password': '1234567',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='weakpw').exists())

    def test_reset_password(self):
        self.client.force_login(self.superuser)
        employee = User.objects.create_user('resetme', password='old-pass-123')
        employee.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        self.client.post(reverse('employee_reset_password', args=[employee.pk]), {'password': 'Br4ndNewPass!'})
        employee.refresh_from_db()
        self.assertTrue(employee.check_password('Br4ndNewPass!'))

    def test_toggle_active(self):
        self.client.force_login(self.superuser)
        employee = User.objects.create_user('togglee', password='test-pass-123')
        employee.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        self.assertTrue(employee.is_active)
        self.client.post(reverse('employee_toggle_active', args=[employee.pk]))
        employee.refresh_from_db()
        self.assertFalse(employee.is_active)
        self.client.post(reverse('employee_toggle_active', args=[employee.pk]))
        employee.refresh_from_db()
        self.assertTrue(employee.is_active)

    def test_delete_employee_with_no_history(self):
        self.client.force_login(self.superuser)
        employee = User.objects.create_user('deleteme', password='test-pass-123')
        employee.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        self.client.post(reverse('employee_delete', args=[employee.pk]))
        self.assertFalse(User.objects.filter(pk=employee.pk).exists())

    def test_superuser_in_employee_group_is_never_listed_or_manageable(self):
        # A superuser could end up with the Employee group too (e.g. picked up
        # via /admin/, or a test fixture that adds every group). They must
        # never appear in this list, or a misclick could deactivate/delete
        # the account the admin is currently logged in as.
        self.superuser.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        self.client.force_login(self.superuser)

        listing = self.client.get(reverse('employee_list'))
        # The username legitimately appears in the topbar (who's logged in) —
        # what matters is the table itself, which must list no one.
        self.assertContains(listing, 'No employee accounts yet')

        for name, kwargs in (
            ('employee_reset_password', {}), ('employee_toggle_active', {}), ('employee_delete', {}),
        ):
            response = self.client.post(reverse(name, args=[self.superuser.pk]), kwargs)
            self.assertEqual(response.status_code, 404, f'{name} must not operate on a superuser')

        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())

    def test_delete_employee_with_history_is_protected(self):
        from customers.models import Customer
        from invoices.models import Invoice

        self.client.force_login(self.superuser)
        employee = User.objects.create_user('busyemployee', password='test-pass-123')
        employee.groups.add(Group.objects.get(name=GROUP_EMPLOYEE))
        customer = Customer.objects.create(first_name='Record')
        Invoice.objects.create(customer=customer, created_by=employee)

        response = self.client.post(reverse('employee_delete', args=[employee.pk]), follow=True)
        self.assertTrue(User.objects.filter(pk=employee.pk).exists())
        shown = [str(m) for m in response.context['messages']]
        self.assertTrue(any('deactivate' in m.lower() for m in shown))
