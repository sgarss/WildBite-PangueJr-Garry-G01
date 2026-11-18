from decimal import Decimal

from django import forms

from .models import MenuItem, Order

MAX_ORDER_QUANTITY = 99


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ('name', 'description', 'category', 'price', 'is_available')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError('Enter a menu item name.')
        return name

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= Decimal('0'):
            raise forms.ValidationError('Price must be greater than zero.')
        return price


class OrderSelectionForm(forms.Form):
    def __init__(self, *args, menu_items=None, existing_quantities=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.menu_items = list(menu_items if menu_items is not None else MenuItem.objects.none())
        self.existing_quantities = existing_quantities or {}

        for item in self.menu_items:
            self.fields[f'quantity_{item.pk}'] = forms.IntegerField(
                label=f'{item.name} — ${item.price:.2f}',
                help_text=item.description,
                min_value=0,
                max_value=MAX_ORDER_QUANTITY,
                required=False,
                initial=self.existing_quantities.get(item.pk, 0),
                widget=forms.NumberInput(attrs={'min': 0, 'max': MAX_ORDER_QUANTITY}),
            )

    def clean(self):
        cleaned_data = super().clean()
        selected = {
            item: quantity
            for item in self.menu_items
            if (quantity := cleaned_data.get(f'quantity_{item.pk}') or 0) > 0
        }
        if not selected:
            raise forms.ValidationError('Choose at least one menu item.')

        for item, quantity in selected.items():
            old_quantity = self.existing_quantities.get(item.pk, 0)
            if not item.is_available and quantity > old_quantity:
                self.add_error(
                    f'quantity_{item.pk}',
                    'This item is no longer available and cannot be added to your order.',
                )
        self.selected_quantities = selected
        return cleaned_data


class OrderStatusForm(forms.Form):
    status = forms.ChoiceField()

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        next_statuses = {
            Order.Status.PENDING: (Order.Status.ACCEPTED, Order.Status.CANCELLED),
            Order.Status.ACCEPTED: (Order.Status.PREPARING, Order.Status.CANCELLED),
            Order.Status.PREPARING: (Order.Status.READY,),
            Order.Status.READY: (Order.Status.COMPLETED,),
        }
        choices = [
            (status, Order.Status(status).label)
            for status in next_statuses.get(order.status, ())
        ]
        self.fields['status'].choices = choices
        self.fields['status'].required = bool(choices)
        if not choices:
            self.fields['status'].disabled = True
