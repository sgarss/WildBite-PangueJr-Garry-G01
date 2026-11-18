from django import forms

from .models import Category, MenuItem


# Names must be unique in any letter case
def check_unique_name(form, model, label):
    name = form.cleaned_data.get("name")
    taken = model.objects.filter(name__iexact=name).exclude(pk=form.instance.pk).exists()
    if taken:
        raise forms.ValidationError(f"A {label} with this name already exists.")
    return name


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "description")
        help_texts = {"description": "Optional."}

    def clean_name(self):
        return check_unique_name(self, Category, "category")


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ("category", "name", "description", "price", "is_available")
        labels = {"price": "Price (₱)", "is_available": "Available to order"}
        help_texts = {"description": "Optional."}
        error_messages = {"category": {"required": "Please choose a category."}}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "price": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].empty_label = "Select a category"

    def clean_name(self):
        return check_unique_name(self, MenuItem, "menu item")

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is not None and price <= 0:
            raise forms.ValidationError("Price must be greater than zero.")
        return price
