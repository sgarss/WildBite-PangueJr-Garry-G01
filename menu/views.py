from django.contrib import messages
from django.db.models import Count, ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import role_required
from accounts.models import User

from .forms import CategoryForm
from .models import Category

staff_only = role_required(User.Role.STAFF)


@staff_only
def category_list(request):
    categories = Category.objects.annotate(item_count=Count("menu_items"))
    return render(request, "menu/category_list.html", {"categories": categories})


# Add (no pk) or edit a category
@staff_only
def category_form(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated." if category else "Category added.")
            return redirect("menu:category_list")
        messages.error(request, "Please fix the errors below.")
    else:
        form = CategoryForm(instance=category)

    return render(request, "menu/form.html", {
        "form": form,
        "title": "Edit category" if category else "Add category",
        "cancel_url": reverse("menu:category_list"),
    })


@staff_only
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        try:
            category.delete()
        except (ProtectedError, RestrictedError):
            messages.error(request, f'"{category}" still has menu items, so it can\'t be deleted.')
        else:
            messages.success(request, f'"{category}" was deleted.')
        return redirect("menu:category_list")

    return render(request, "menu/confirm_delete.html", {
        "object": category,
        "kind": "category",
        "cancel_url": reverse("menu:category_list"),
    })
