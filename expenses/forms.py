from django import forms
from django.utils import timezone

from core.forms import BootstrapModelForm, OptionalWithDefaultMixin, TableRowFormMixin

from .models import ExpenseLine, ExpenseReport

# Dropdown sentinel for "a category that isn't in the list yet" — picking it
# reveals the free-text box.
OTHER_CATEGORY = '__other__'


class ExpenseReportForm(BootstrapModelForm):
    class Meta:
        model = ExpenseReport
        fields = ('name', 'report_date', 'notes')
        widgets = {
            'report_date': forms.DateInput(attrs={'type': 'date'}),
            'name': forms.TextInput(attrs={'placeholder': 'e.g. October shop supplies'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank means today, so a report can be filed without touching the date.
        self.fields['report_date'].required = False
        if not self.instance.pk:
            self.initial['report_date'] = timezone.localdate()

    def clean_report_date(self):
        return self.cleaned_data.get('report_date') or timezone.localdate()


class ExpenseLineForm(OptionalWithDefaultMixin, TableRowFormMixin, BootstrapModelForm):
    """One description + amount row. The category is a hidden field that the
    page fills in from the dropdown of the category section the row sits in."""

    optional_with_default = ('amount',)

    class Meta:
        model = ExpenseLine
        fields = ('description', 'category', 'amount', 'reference')
        widgets = {'category': forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['placeholder'] = 'What was it for?'
        self.fields['amount'].widget.attrs.update(
            {'min': 0, 'step': '0.01', 'placeholder': '0.00'}
        )
        self.fields['reference'].widget.attrs['placeholder'] = 'Receipt, cheque, transfer…'
        if not self.instance.pk:
            # Show an empty amount box rather than the model default of 0.00.
            # Both initials have to go: self.initial falls back to the field's
            # own initial, and either one left in place would make every blank
            # row look like it had been filled in.
            self.fields['amount'].initial = None
            self.initial.pop('amount', None)

    def has_changed(self):
        if not self.instance.pk:
            # The page fills the hidden category in for every row, so a row only
            # counts as filled in once something was actually typed into it.
            return bool(set(self.changed_data) & {'description', 'amount'})
        return super().has_changed()


ExpenseLineFormSet = forms.inlineformset_factory(
    ExpenseReport, ExpenseLine, form=ExpenseLineForm, extra=1, can_delete=True,
)

# The shape group_line_forms() returns, for the "add a section" template row.
BLANK_GROUP = {'category': '', 'selected': '', 'custom': '', 'forms': [], 'open': False}


def group_line_forms(formset, options):
    """Bucket the formset's rows by category for the accordion (first-seen order).

    `selected` is the dropdown choice: a known option, "" for none, or OTHER_CATEGORY
    when the category is one the dropdown doesn't list yet (shown in the text box).
    Exactly one group is flagged open: the first with errors, otherwise the first.
    """
    known = {option.lower(): option for option in options}
    groups = {}
    for form in formset.forms:
        category = (form['category'].value() or '').strip()
        key = category.lower()
        group = groups.setdefault(key, {
            'category': category,
            'selected': known.get(key, OTHER_CATEGORY if category else ''),
            'custom': '' if key in known else category,
            'forms': [],
            'open': False,
        })
        group['forms'].append(form)

    groups = list(groups.values())
    opened = next((g for g in groups if any(f.errors for f in g['forms'])), None)
    if opened is None and groups:
        opened = groups[0]
    if opened is not None:
        opened['open'] = True
    return groups
