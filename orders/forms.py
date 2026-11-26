from datetime import timedelta

from django import forms

from .models import OrderStatus

MAX_QUANTITY = 20
MAX_REPORT_DAYS = 366


# One quantity box per menu item
class OrderItemsForm(forms.Form):
    def __init__(self, *args, menu_items, initial_quantities=None, **kwargs):
        super().__init__(*args, **kwargs)
        initial_quantities = initial_quantities or {}
        self.menu_items = list(menu_items)
        for item in self.menu_items:
            self.fields[f"qty_{item.pk}"] = forms.IntegerField(
                label=item.name,
                min_value=0,
                max_value=MAX_QUANTITY,
                required=False,
                initial=initial_quantities.get(item.pk, 0),
                widget=forms.NumberInput(attrs={"class": "qty-input", "min": 0, "max": MAX_QUANTITY}),
            )

    # Menu item and its quantity box, for the template
    def rows(self):
        return [{"item": item, "field": self[f"qty_{item.pk}"]} for item in self.menu_items]

    def clean(self):
        cleaned_data = super().clean()
        self.quantities = {}
        for item in self.menu_items:
            quantity = cleaned_data.get(f"qty_{item.pk}")
            if quantity:
                self.quantities[item.pk] = quantity
        if not self.errors and not self.quantities:
            raise forms.ValidationError("Choose at least one menu item.")
        return cleaned_data


class OrderFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Order number",
        widget=forms.SearchInput(attrs={"placeholder": "e.g. WB-261118-001"}),
    )
    status = forms.ChoiceField(
        choices=[("", "All statuses")] + OrderStatus.choices,
        required=False,
    )
    date = forms.DateField(
        required=False,
        label="Order date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )


class SalesReportForm(forms.Form):
    start = forms.DateField(label="From", widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(label="To", widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        if start and end:
            if start > end:
                raise forms.ValidationError("The start date must be on or before the end date.")
            # Keep the report to about one year
            if end - start >= timedelta(days=MAX_REPORT_DAYS):
                raise forms.ValidationError(f"Choose a range of {MAX_REPORT_DAYS} days or less.")
        return cleaned_data
