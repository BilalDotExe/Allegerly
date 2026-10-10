import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import connections, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.permissions import GROUP_EMPLOYEE
from customers.models import Customer
from .db import active_db, atomic, business_context
from .middleware import BUSINESS_SESSION_KEY
from .models import Business
from .services import _adopt_users, create_business, default_suffix

PASSWORD = "Correct-Horse-91"
TMP_DIR = tempfile.mkdtemp(prefix="allegderly-businesses-")
BUSINESS_ALIASES = frozenset({"business_acme", "business_bolt"})
LOGIN_ERROR = "Username or password is incorrect."


@override_settings(BUSINESS_DB_DIR=TMP_DIR)
class BusinessIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Django refuses queries to aliases a test hasn't declared; these are
        # only created here, so declare them now. Each test then also runs in
        # a rolled-back transaction on them.
        cls.databases = cls.databases | BUSINESS_ALIASES
        cls.acme = create_business("acme", "Acme Soap", "acme_boss", PASSWORD)    # suffix: as
        cls.bolt = create_business("bolt", "Bolt Candles", "bolt_boss", PASSWORD)  # suffix: bc
        with business_context(cls.acme):
            Customer.objects.create(first_name="Acme customer")
            User.objects.create_user("john@as", password=PASSWORD)
        with business_context(cls.bolt):
            User.objects.create_user("john@bc", password=PASSWORD)

    @classmethod
    def tearDownClass(cls):
        # The class-level rollback only knows about 'default', so the business
        # aliases must be gone before Django tears down.
        for alias in BUSINESS_ALIASES:
            connections[alias].close()
            del connections.settings[alias]
        cls.databases = cls.databases - BUSINESS_ALIASES
        super().tearDownClass()
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _login(self, username, password=PASSWORD):
        return self.client.post(reverse("login"), {"username": username, "password": password})

    # --- data separation ---------------------------------------------------

    def test_each_business_sees_only_its_own_data(self):
        with business_context(self.acme):
            self.assertEqual(Customer.objects.count(), 1)
        with business_context(self.bolt):
            self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 0)  # Nor does the control database.

    def test_new_business_has_only_the_employee_group(self):
        with business_context(self.bolt):
            self.assertEqual(list(Group.objects.values_list("name", flat=True)), [GROUP_EMPLOYEE])

    def test_atomic_opens_its_transaction_on_the_business_database(self):
        with business_context(self.acme):
            self.assertEqual(active_db(), "business_acme")
            with atomic():
                self.assertTrue(transaction.get_connection("business_acme").in_atomic_block)

    # --- sign-in -----------------------------------------------------------

    def test_owner_signs_in_with_just_a_username(self):
        self.assertRedirects(self._login("acme_boss"), reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.session[BUSINESS_SESSION_KEY], "acme")
        self.assertContains(self.client.get(reverse("customers:list")), "Acme customer")

    def test_employee_signs_in_with_name_and_suffix_in_any_case(self):
        self._login("John@AS")
        self.assertEqual(self.client.session[BUSINESS_SESSION_KEY], "acme")

    def test_same_first_name_in_two_businesses_are_separate_accounts(self):
        self._login("john@bc")
        self.assertEqual(self.client.session[BUSINESS_SESSION_KEY], "bolt")

    def test_employee_password_from_another_business_is_rejected(self):
        with business_context(self.bolt):
            user = User.objects.get(username="john@bc")
            user.set_password("Other-Pass-77!")
            user.save()
        self.assertContains(self._login("john@bc", PASSWORD), LOGIN_ERROR)
        self.assertNotIn(BUSINESS_SESSION_KEY, self.client.session)

    def test_unknown_names_get_the_generic_error(self):
        for username in ("nobody", "nobody@as", "john@nope", "john"):
            self.assertContains(self._login(username), LOGIN_ERROR)

    def test_wrong_password_gets_the_generic_error(self):
        self.assertContains(self._login("acme_boss", "wrong"), LOGIN_ERROR)

    def test_lockout_in_one_business_does_not_affect_another(self):
        for _ in range(6):
            self._login("acme_boss", "wrong")
        self._login("acme_boss")
        self.assertNotIn(BUSINESS_SESSION_KEY, self.client.session)
        self.assertRedirects(self._login("bolt_boss"), reverse("dashboard"), fetch_redirect_response=False)

    def test_session_without_a_business_is_signed_out(self):
        self.client.force_login(User.objects.create_superuser("legacy", "", PASSWORD))
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_deactivating_a_business_signs_its_users_out(self):
        self._login("acme_boss")
        Business.objects.filter(slug="acme").update(is_active=False)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(BUSINESS_SESSION_KEY, self.client.session)

    # --- employee accounts -------------------------------------------------

    def _create_employee(self, username):
        return self.client.post(reverse("employee_create"), {
            "username": username, "first_name": "", "last_name": "", "password": "",
        })

    def test_employee_username_gets_the_fixed_suffix(self):
        self._login("acme_boss")
        self.assertContains(self.client.get(reverse("employee_create")), "@as")
        self.assertRedirects(self._create_employee("Mary"), reverse("employee_list"))
        with business_context(self.acme):
            self.assertTrue(User.objects.filter(username="mary@as", groups__name=GROUP_EMPLOYEE).exists())

    def test_employee_name_cannot_carry_its_own_suffix(self):
        self._login("acme_boss")
        self.assertContains(self._create_employee("mary@bc"), "Leave out the @ part")
        with business_context(self.acme):
            self.assertFalse(User.objects.filter(username__startswith="mary").exists())

    def test_employee_name_already_taken_is_rejected(self):
        self._login("acme_boss")
        self.assertContains(self._create_employee("john"), "already taken")

    # --- business rules ----------------------------------------------------

    def test_owner_username_must_be_unique_across_businesses(self):
        with self.assertRaises(ValidationError):
            create_business("third", "Third Co", "acme_boss", PASSWORD)

    def test_suffix_must_be_unique_across_businesses(self):
        with self.assertRaises(ValidationError):
            create_business("third", "Third Co", "third_boss", PASSWORD, suffix="as")

    def test_owner_username_cannot_contain_an_at_sign(self):
        with self.assertRaises(ValidationError):
            create_business("third", "Third Co", "boss@third", PASSWORD)

    def test_suffix_cannot_be_changed(self):
        self.acme.suffix = "zz"
        with self.assertRaises(ValidationError):
            self.acme.save()

    def test_default_suffix_is_the_name_initials(self):
        self.assertEqual(default_suffix("Totally Real Shipping Co"), "trsc")
        self.assertEqual(default_suffix("Acme"), "acme")

    def test_adopting_a_database_renames_its_employees(self):
        with business_context(self.acme):
            User.objects.create_user("Legacy", password=PASSWORD)
            _adopt_users(Business(slug="x", suffix="as", owner_username="acme_boss"))
            self.assertTrue(User.objects.filter(username="legacy@as").exists())

    def test_adopting_a_database_with_other_superusers_is_refused(self):
        with business_context(self.acme):
            User.objects.create_superuser("extra", "", PASSWORD)
            with self.assertRaises(ValidationError):
                _adopt_users(Business(slug="x", suffix="as", owner_username="acme_boss"))
