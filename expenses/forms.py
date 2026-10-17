from django import forms
from django.utils import timezone

from core.forms import BootstrapModelForm, OptionalWithDefaultMixin, TableRowFormMixin
from .models import ExpenseLine, ExpenseReport

OTHER_CATEGORY = "__other__"


class ExpenseReportForm(BootstrapModelForm):
    class Meta:
        model = ExpenseReport
        fields = ["name", "report_date", "notes"]
        widgets = {
            "report_date": forms.DateInput(attrs={"type": "date"}),
            "name": forms.TextInput(attrs={"placeholder": "e.g. October shop supplies"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the name is required; the date falls back to today.
        self.fields["report_date"].required = False
        if not self.instance.pk:
            self.fields["report_date"].initial = timezone.localdate()

    def clean_report_date(self):
        return self.cleaned_data.get("report_date") or timezone.localdate()


class ExpenseLineForm(OptionalWithDefaultMixin, TableRowFormMixin, BootstrapModelForm):
    """One description + amount row. The category is a hidden field that the
    page fills in from the dropdown of the category section the row sits in."""

    optional_with_default = ("amount",)

    class Meta:
        model = ExpenseLine
        fields = ["description", "category", "amount", "reference"]
        widgets = {"category": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["placeholder"] = "What was it for?"
        self.fields["amount"].widget.attrs.update({"min": 0, "step": "0.01", "placeholder": "0.00"})
        self.fields["reference"].widget.attrs["placeholder"] = "Receipt, cheque, transfer…"
        if not self.instance.pk:
            self.initial.pop("amount", None)
            self.fields["amount"].initial = None

    def has_changed(self):
        if not self.instance.pk:
            return bool({"description", "amount"} & set(self.changed_data))
        return super().has_changed()


ExpenseLineFormSet = forms.inlineformset_factory(
    ExpenseReport,
    ExpenseLine,
    form=ExpenseLineForm,
    extra=0,
    can_delete=True,
)

BLANK_GROUP = {"category": "", "selected": "", "custom": "", "forms": [], "open": False}


def group_line_forms(formset, options):
    """Bucket the formset's rows by category for the accordion (first-seen order).

    `selected` is the dropdown choice: a known option, "" for none, or OTHER_CATEGORY
    when the category is one the dropdown doesn't list yet (shown in the text box).
    Exactly one group is flagged open: the first with errors, otherwise the first.
    """
    known = {option.lower(): option for option in options}
    groups = {}
    for line_form in formset.forms:
        raw = (line_form["category"].value() or "").strip()
        group = groups.get(raw.lower())
        if group is None:
            match = known.get(raw.lower(), "")
            group = groups[raw.lower()] = {
                "category": raw,
                "selected": match if match or not raw else OTHER_CATEGORY,
                "custom": raw if raw and not match else "",
                "forms": [],
                "open": False,
            }
        group["forms"].append(line_form)
    result = list(groups.values())
    flagged = next((g for g in result if any(f.errors for f in g["forms"])), None)
    target = flagged or (result[0] if result else None)
    if target:
        target["open"] = True
    return result
