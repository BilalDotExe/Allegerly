from django import forms


class BootstrapFormMixin:
    """Apply Bootstrap 5 input classes to all Django form widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
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


class BootstrapModelForm(BootstrapFormMixin, forms.ModelForm):
    pass


class BootstrapForm(BootstrapFormMixin, forms.Form):
    pass
