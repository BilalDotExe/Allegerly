from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from core.money import money, zero_money
from core.permissions import (
    GROUP_ADMIN,
    GROUP_STAFF,
    GROUP_VIEW_ONLY,
    can_view,
    is_admin,
    is_staff_user,
)


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
