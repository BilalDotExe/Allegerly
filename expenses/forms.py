from django import forms
from django.utils import timezone

from core.forms import BootstrapModelForm, OptionalWithDefaultMixin, TableRowFormMixin
from .models import ExpenseLine, ExpenseReport

# The <datalist> every category box draws its suggestions from.
CATEGORY_LIST_ID = "expense-category-options"


class ExpenseReportForm(BootstrapModelForm):
    class Meta:
        model = ExpenseReport
        fields = ["name", "report_date", "notes"]
        labels = {"name": "Name", "report_date": "Expense date"}
        help_texts = {
            "name": 'Optional. Left blank, it is saved as "Expense" and the date.',
            "report_date": "Counts toward that month's reports and dashboard.",
        }
        widgets = {
            "report_date": forms.DateInput(attrs={"type": "date"}),
            "name": forms.TextInput(attrs={"placeholder": "e.g. October shop supplies"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the date is required (it starts on today); a blank name is filled in
        # from the date when the expense is saved (see ExpenseReport.save).
        self.fields["name"].required = False
        if not self.instance.pk:
            self.fields["report_date"].initial = timezone.localdate()


class ExpenseLineForm(OptionalWithDefaultMixin, TableRowFormMixin, BootstrapModelForm):
    """One line: category, description, amount, reference. Nothing is required;
    a blank amount is saved as 0.00."""

    optional_with_default = ("amount",)

    class Meta:
        model = ExpenseLine
        fields = ["category", "description", "amount", "reference"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].widget.attrs.update({
            "list": CATEGORY_LIST_ID, "autocomplete": "off", "placeholder": "Choose or type…",
            "class": self.fields["category"].widget.attrs.get("class", "") + " expense-category",
        })
        self.fields["description"].widget.attrs["placeholder"] = "What was it for?"
        self.fields["amount"].widget.attrs.update({"min": 0, "step": "0.01", "placeholder": "0.00", "inputmode": "decimal"})
        self.fields["reference"].widget.attrs["placeholder"] = "Receipt, cheque…"
        if not self.instance.pk:
            self.initial.pop("amount", None)
            self.fields["amount"].initial = None

    def has_changed(self):
        # A new row only counts once something besides the category is typed, so a
        # category picked on an otherwise empty row doesn't save a blank line.
        if not self.instance.pk:
            return bool({"description", "amount", "reference"} & set(self.changed_data))
        return super().has_changed()


ExpenseLineFormSet = forms.inlineformset_factory(
    ExpenseReport,
    ExpenseLine,
    form=ExpenseLineForm,
    extra=0,
    can_delete=True,
)
