from django import forms

from .models import Category


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
