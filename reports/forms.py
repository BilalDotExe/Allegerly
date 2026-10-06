from django import forms
from core.forms import BootstrapForm


class DateRangeForm(BootstrapForm):
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))