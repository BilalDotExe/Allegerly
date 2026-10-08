from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from core.models import CompanyProfile


class BootstrapFormMixin:
    """Apply Bootstrap 5 input classes to all Django form widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.URLInput):
                # Plain text, not type="url" — browsers silently block submission of a
                # bare domain like "example.com" under native URL validation, with no
                # visible error. Django's URLField already prepends https:// server-side.
                field.widget = widget = forms.TextInput(attrs=widget.attrs)
            if isinstance(widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.RadioSelect)):
                css_class = "form-select" if isinstance(widget, forms.Select) else "form-check-input"
            else:
                css_class = "form-control"
            existing = widget.attrs.get("class", "").split()
            if css_class not in existing:
                existing.append(css_class)
            widget.attrs["class"] = " ".join(existing)


# Browser autofill tokens, keyed by the field name we use for that kind of data.
# Address fields are looked up by their suffix so billing_city and shipping_city
# both resolve, each scoped with the matching "billing"/"shipping" prefix.
_CONTACT_TOKENS = {
    "first_name": "given-name",
    "middle_name": "additional-name",
    "last_name": "family-name",
    "company_name": "organization",
    "name": "organization",
    "contact_person": "name",
    "email": "email",
    "phone": "tel",
    "website": "url",
}
_ADDRESS_TOKENS = {
    "line1": "address-line1",
    "line2": "address-line2",
    "city": "address-level2",
    "state": "address-level1",
    "postal_code": "postal-code",
    "country": "country-name",
    "address_line1": "address-line1",
    "address_line2": "address-line2",
}


class ContactAutocompleteMixin:
    """Let the browser autofill names, phones, emails and addresses.

    Staff re-enter the same customer and vendor details constantly; without
    these tokens the browser offers nothing. Phone also becomes type="tel" so
    phones show a number pad instead of a full keyboard.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            token = self._autocomplete_token(name)
            if token:
                field.widget.attrs.setdefault("autocomplete", token)
            if name.endswith("phone"):
                # Must be input_type, not an attrs["type"]: Django renders the
                # widget's own type first and a second type= attribute is ignored.
                field.widget.input_type = "tel"
                field.widget.attrs.setdefault("inputmode", "tel")
            if name.endswith(("email", "postal_code", "website", "tax_id", "sku")):
                field.widget.attrs.setdefault("spellcheck", "false")

    @staticmethod
    def _autocomplete_token(name):
        if name in _CONTACT_TOKENS:
            return _CONTACT_TOKENS[name]
        for prefix, scope in (("billing_", "billing"), ("shipping_", "shipping")):
            if name.startswith(prefix):
                token = _ADDRESS_TOKENS.get(name[len(prefix):])
                return f"{scope} {token}" if token else None
        return _ADDRESS_TOKENS.get(name)


class TableRowFormMixin:
    """For forms rendered as a row inside a table, where the column header is the
    only visible label.

    A `<th>` is not programmatically tied to an input, so without this a screen
    reader reads those cells as unnamed edit boxes. The row number keeps the
    names distinct when a formset repeats the same columns.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        row = self.prefix.rsplit("-", 1)[-1] if self.prefix else ""
        suffix = f", line {int(row) + 1}" if row.isdigit() else ""
        for field in self.fields.values():
            field.widget.attrs.setdefault("aria-label", f"{field.label}{suffix}")


class BootstrapModelForm(BootstrapFormMixin, forms.ModelForm):
    pass


class BootstrapForm(BootstrapFormMixin, forms.Form):
    pass


class CompanyProfileForm(ContactAutocompleteMixin, BootstrapModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            "name", "phone", "email", "website", "tax_id",
            "address_line1", "address_line2", "city", "state", "postal_code", "country",
            "invoice_footer",
        ]


# The password field is plain text, not type="password": the superuser setting
# it needs to read back what they typed or what "Generate" just filled in, and
# the plaintext is shown once on the next page anyway (core.views.employee_list).
_PASSWORD_ATTRS = {"autocomplete": "new-password", "spellcheck": "false", "class": "temp-password-field"}


def _check_password_strength(form, password, user_stub):
    try:
        validate_password(password, user=user_stub)
    except ValidationError as exc:
        form.add_error("password", exc)


class EmployeeCreateForm(BootstrapForm):
    username = forms.CharField(
        max_length=150, help_text="What they'll type to sign in — no spaces.",
        widget=forms.TextInput(attrs={"autocomplete": "username", "spellcheck": "false", "autocapitalize": "none"}),
    )
    first_name = forms.CharField(max_length=150, required=False,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    last_name = forms.CharField(max_length=150, required=False,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    password = forms.CharField(
        max_length=128, required=False, widget=forms.TextInput(attrs=_PASSWORD_ATTRS),
        help_text="Leave blank, or click Generate, for a random 8-character password.",
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not username or " " in username:
            raise ValidationError("Usernames can't be blank or contain spaces.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            stub = User(
                username=cleaned.get("username", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            _check_password_strength(self, password, stub)
        return cleaned


class EmployeePasswordResetForm(BootstrapForm):
    password = forms.CharField(
        max_length=128, required=False, widget=forms.TextInput(attrs=_PASSWORD_ATTRS),
        help_text="Leave blank, or click Generate, for a random 8-character password.",
    )

    def __init__(self, *args, employee, **kwargs):
        self.employee = employee
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            _check_password_strength(self, password, self.employee)
        return password
