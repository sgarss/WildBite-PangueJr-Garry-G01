from django import forms

from .models import OrderStatus

MAX_QUANTITY = 20


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
